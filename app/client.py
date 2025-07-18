import os
import json
import sys
from websockets import Subprotocol
from websockets.sync.client import connect
import logging
import requests
from dotenv import load_dotenv
import keyring
import re
import threading

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BitCraft:
    SERVICE_NAME = "BitCraftAPI"
    DEFAULT_SUBPROTOCOL = 'v1.json.spacetimedb'
    AUTH_API_BASE_URL = "https://api.bitcraftonline.com/authentication"

    def _get_data_directory(self):
        """
        Get the directory where data files should be stored.
        Returns the executable's directory when bundled, or the script directory in development.
        """
        if getattr(sys, 'frozen', False):
            # Running as bundled executable
            return os.path.dirname(sys.executable)
        else:
            # Running as script
            return os.path.dirname(__file__)

    def __init__(self):
        self.host = os.getenv('BITCRAFT_SPACETIME_HOST', 'bitcraft-early-access.spacetimedb.com')
        self.uri = '{scheme}://{host}/v1/database/{module}/{endpoint}'
        self.proto = Subprotocol(self.DEFAULT_SUBPROTOCOL) 
        self.ws_connection = None
        self.module = None
        self.endpoint = None
        self.ws_uri = None
        self.headers = {}
        
        # Thread lock for WebSocket operations
        self.ws_lock = threading.Lock()

        # Initialize cached reference data to None
        self._building_desc = None
        self._building_function_type_mapping_desc = None
        self._building_type_desc = None

        # Load non-sensitive user data from file
        self.load_user_data_from_file()

        # Sensitive data will be loaded/stored via keyring, not directly in __init__
        self.email = self._get_credential_from_keyring('email') or self.email  # Prefer keyring email over file
        self.auth = self._get_credential_from_keyring('authorization_token')

    def _get_credential_from_keyring(self, key_name: str) -> str | None:
        """Retrieves a credential from the system keyring."""
        try:
            credential = keyring.get_password(self.SERVICE_NAME, key_name)
            if credential:
                logging.info(f"Credential '{key_name}' loaded from keyring.")
            else:
                logging.warning(f"Credential '{key_name}' not found in keyring.")
            return credential
        except keyring.errors.NoKeyringError:
            logging.warning("No keyring backend found. Credentials will not be securely stored.")
            return None
        except Exception as e:
            logging.error(f"Error retrieving '{key_name}' from keyring: {e}")
            return None

    def _set_credential_in_keyring(self, key_name: str, value: str):
        """Stores a credential in the system keyring."""
        try:
            keyring.set_password(self.SERVICE_NAME, key_name, value)
            logging.info(f"Credential '{key_name}' stored in keyring.")
        except keyring.errors.NoKeyringError:
            logging.warning("No keyring backend found. Cannot securely store credentials.")
        except Exception as e:
            logging.error(f"Error storing '{key_name}' in keyring: {e}")

    def _delete_credential_from_keyring(self, key_name: str):
        """Deletes a credential from the system keyring."""
        try:
            keyring.delete_password(self.SERVICE_NAME, key_name)
            logging.info(f"Credential '{key_name}' deleted from keyring.")
        except keyring.errors.NoKeyringError:
            logging.warning("No keyring backend found. Cannot delete credentials.")
        except keyring.errors.PasswordDeleteError:
            logging.warning(f"Credential '{key_name}' not found in keyring to delete.")
        except Exception as e:
            logging.error(f"Error deleting '{key_name}' from keyring: {e}")


    def _load_reference_data(self, filename: str) -> dict | list | None:
        """Loads reference data from a JSON file."""
        if getattr(sys, 'frozen', False):
            # Running as bundled executable - references are in the same directory
            file_path = os.path.join(os.path.dirname(sys.executable), 'references', filename)
        else:
            # Running as script
            file_path = os.path.join(os.path.dirname(__file__), 'references', filename)
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Reference file not found: {filename} at {file_path}")
            return None
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from: {filename}")
            return None

    def update_user_data_file(self, key: str, value: str):
        """
        Updates non-sensitive user data in player_data.json.
        Sensitive data is handled by keyring.
        """
        file_path = os.path.join(self._get_data_directory(), 'player_data.json')
        data = {}
        try:
            # Read existing data
            with open(file_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            logging.warning("player_data.json not found. Creating a new one.")
        except json.JSONDecodeError:
            logging.warning("player_data.json is malformed. Overwriting with new data.")
            data = {} # Reset data if malformed

        try:
            # Update data and write back
            data[key] = value
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            logging.info(f"User data file updated: {key} in {file_path}")
        except Exception as e:
            logging.error(f"Error writing to player_data.json: {e}")

    def load_user_data_from_file(self):
        """Loads non-sensitive user data from player_data.json."""
        try:
            with open(os.path.join(self._get_data_directory(), 'player_data.json'), 'r') as f:
                data = json.load(f)
                self.email = data.get('email')
                self.region = data.get('region')
                self.player_name = data.get('player_name')
                # Host from file takes precedence over .env if available
                self.host = data.get('host', self.host)
                logging.info("Non-sensitive user data loaded successfully from file.")
        except FileNotFoundError:
            logging.warning("player_data.json not found. Some user data might be missing.")
            self.email = None
            self.region = None
            self.player_name = None
        except json.JSONDecodeError:
            logging.error("player_data.json is corrupted or empty. Please check the file.")
            self.email = None
            self.region = None
            self.player_name = None

    def _is_valid_email(self, email: str) -> bool:
        """Performs a basic regex validation for an email address."""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, email) is not None

    def get_access_code(self, email: str) -> bool:
        """
        Requests a new access code from the API. Does NOT prompt the user for input.
        Returns True if the request was successful, False otherwise.
        """
        if not email:
            raise ValueError("Email is required to request an access code.")

        if not self._is_valid_email(email):
            raise ValueError(f"Invalid email format: {email}")

        logging.info(f"Requesting new access code for {email}...")

        encoded_email = requests.utils.quote(email)
        uri = f"{self.AUTH_API_BASE_URL}/request-access-code?email={encoded_email}"
        try:
            response = requests.post(uri)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            logging.info("Access Code request was successful! Check your email for the code.")
            return True # Indicate success
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error requesting access code: {http_err} - {response.text}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Network error requesting access code: {req_err}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during access code request: {e}")
        
        return False # Indicate failure

    def get_authorization_token(self, email: str, access_code: str) -> str | None:
        """
        Requests a new authorization token using email and access code.
        Returns the authorization token if obtained, else None.
        """
        if not email:
            raise ValueError("Email is required to request an authorization token.")
        if not access_code:
            raise ValueError("Access code is required to request an authorization token.")
        
        if not self._is_valid_email(email):
            raise ValueError(f"Invalid email format: {email}")

        logging.info("Requesting new authorization token...")

        encoded_email = requests.utils.quote(email)
        uri = f"{self.AUTH_API_BASE_URL}/authenticate?email={encoded_email}&accessCode={access_code}"
        try:
            response = requests.post(uri)
            response.raise_for_status() 
            
            authorization_token = response.json()
            # Store the token and email in keyring and update instance properties
            self._set_credential_in_keyring('authorization_token', f"Bearer {authorization_token}")
            self._set_credential_in_keyring('email', email)
            self.auth = f"Bearer {authorization_token}"
            self.email = email
            logging.info(f"Authorization token received! {self.auth[:15]}...")
            return self.auth

        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error requesting authorization token: {http_err} - {response.text}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Network error requesting authorization token: {req_err}")
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON response for authorization token.")
        except Exception as e:
            logging.error(f"An unexpected error occurred during authorization token request: {e}")
        
        return None # Return None if token could not be obtained

    def authenticate(self, email: str = None, access_code: str = None) -> bool:
        """
        Provides a unified method for authentication.
        Expects both email and access_code to be provided if a new token is needed.
        If email is not provided, it attempts to use self.email.
        Returns True on successful authentication, False otherwise.
        """
        # Prioritize arguments over instance attributes for the current authentication attempt
        effective_email = email if email is not None else self.email

        if not effective_email:
            logging.error("Authentication failed: Email is required.")
            return False
        
        if not self._is_valid_email(effective_email):
            logging.error(f"Authentication failed: Invalid email format: {effective_email}")
            return False

        # If we already have an auth token and no access_code is given (meaning we're trying to re-use)
        if self.auth and access_code is None: # This implies using pre-existing auth
            logging.info("Authorization token already exists. Assuming authenticated.")
            return True # Consider already authenticated if token exists

        # If we need to get a new auth token (either no auth, or new access_code provided)
        if not access_code:
            logging.error("Authentication failed: Access code is required to obtain a new authorization token.")
            return False

        # Attempt to get a new authorization token using the provided/effective email and access code
        obtained_auth_token = self.get_authorization_token(effective_email, access_code)
        if obtained_auth_token:
            logging.info("Authentication successful!")
            return True
        else:
            logging.error("Authentication failed: Could not obtain authorization token.")
            return False

    def set_host(self, host: str):
        if not host:
            raise ValueError("Host cannot be empty")
        self.host = host
        self.update_user_data_file('host', host) # Store updated host
        logging.info(f"Host set: {host}")

    def set_auth(self, auth: str, email: str = None):
        if not auth:
            raise ValueError("Auth token cannot be empty")
        self.auth = auth
        self._set_credential_in_keyring('authorization_token', auth) # Update keyring
        
        # Also store email if provided
        if email:
            self.email = email
            self._set_credential_in_keyring('email', email)
            
        logging.info(f"Auth token set: {auth[:15]}...")
        if email:
            logging.info(f"Email stored: {email}")

    def set_region(self, region: str):
        if not region:
            raise ValueError("Region cannot be empty")
        self.module = region
        self.update_user_data_file('region', region) # Store updated region
        logging.info(f"Region set: {region}")

    def set_endpoint(self, endpoint: str = "subscribe"):
        if not endpoint:
            raise ValueError("Endpoint cannot be empty")
        self.endpoint = endpoint
        logging.info(f"Endpoint set: {endpoint}")

    def set_websocket_uri(self):
        if not self.host or not self.module or not self.endpoint:
            raise ValueError("Host, module, and endpoint must be set before building WebSocket URI.")
        if not self.auth: # Ensure auth token is available for headers
            raise RuntimeError("Authorization token is not set. Authenticate first.")
        self.ws_uri = self.uri.format(scheme='wss', host=self.host, module=self.module, endpoint=self.endpoint)
        self.headers = {"Authorization": self.auth}
        logging.info(f"WebSocket URI set: {self.ws_uri}")

    def connect_websocket(self):
        with self.ws_lock:
            if not self.ws_uri:
                raise RuntimeError("WebSocket URI is not set. Call set_websocket_uri() first.")
            if self.ws_connection:
                logging.warning("WebSocket connection already exists. Closing existing connection.")
                self.close_websocket()

            try:
                self.ws_connection = connect(
                    self.ws_uri,
                    additional_headers=self.headers,
                    subprotocols=[self.proto],
                    max_size=None,
                    max_queue=None
                )
                # Initial handshake or acknowledgment, if the server sends one immediately
                first_msg = self.ws_connection.recv()
                logging.debug(f"Initial WebSocket handshake message: {first_msg[:100]}...")
                logging.info("WebSocket connection established")
            except Exception as e:
                logging.error(f"Failed to establish WebSocket connection: {e}")
                self.ws_connection = None
                raise # Re-raise to indicate connection failure

    def close_websocket(self):
        with self.ws_lock:
            if self.ws_connection:
                try:
                    self.ws_connection.close()
                    logging.info("WebSocket connection closed")
                except Exception as e:
                    logging.warning(f"Error closing WebSocket: {e}")
                finally:
                    self.ws_connection = None
            else:
                logging.warning("No WebSocket connection to close")

    def _receive_websocket_subscription_data(self, query_name: str): # Removed expected_key as it wasn't used
        """
        Helper method to receive and parse data from a WebSocket subscription.
        Yields each 'insert' row from the 'InitialSubscription' message.
        Note: This method should be called from within a locked context.
        """
        if not self.ws_connection:
            raise RuntimeError("WebSocket connection is not established")

        for msg in self.ws_connection:
            try:
                data = json.loads(msg)
                if 'InitialSubscription' in data:
                    tables = data['InitialSubscription'].get('database_update', {}).get('tables', [])
                    for table in tables:
                        for update in table.get('updates', []):
                            for insert in update.get('inserts', []):
                                try:
                                    row = json.loads(insert)
                                    yield row
                                except json.JSONDecodeError:
                                    logging.error(f"Failed to decode JSON from WebSocket insert: {insert[:100]}...")
                                    continue # Skip malformed insert
                    break # Assuming one initial subscription response for these fetches
                elif 'error' in data: 
                    logging.error(f"WebSocket error received for {query_name}: {data['error']}")
                    return
                # You might want to handle other message types here, e.g., 'TableUpdate' for live changes
            except json.JSONDecodeError:
                logging.error(f"Failed to decode JSON from WebSocket message: {msg[:100]}...")
            except Exception as e:
                logging.error(f"Unexpected error processing WebSocket message: {e}")
        return

    def fetch_user_id(self, username: str) -> str | None:
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            
            sanitized_username = username.lower().replace("'", "''") 

            query_strings = [f"SELECT * FROM player_lowercase_username_state WHERE username_lowercase = '{sanitized_username}';"]
            subscribe = dict(Subscribe=dict(request_id=1, query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)

            for row in self._receive_websocket_subscription_data("fetch_user_id"):
                user_id = row.get("entity_id")
                if user_id:
                    logging.info(f"User ID for {username} found: {user_id}")
                    return user_id
            
            logging.error(f"User ID for {username} not found")
            return None

    def fetch_claim_membership_id_by_user_id(self, user_id: str) -> str | None:
        """
        Fetches the claim membership ID associated with a given user ID via a WebSocket connection.
        This method sends a SQL query over an established WebSocket connection to retrieve the claim membership
        information for the specified user. It listens for the initial subscription response and extracts the
        claim_entity_id from the returned data.
        Args:
            user_id (str): The unique identifier of the user whose claim membership ID is to be fetched.
        Returns:
            str: The claim membership ID associated with the user, or None if not found.
        Raises:
            RuntimeError: If the WebSocket connection is not established.
            ValueError: If the user_id is missing or empty.
        """
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            
            if not user_id:
                raise ValueError("User ID missing.")
            
            sanitized_user_id = str(user_id).replace("'", "''") 

            query_strings = [f"SELECT * FROM claim_member_state WHERE player_entity_id = '{sanitized_user_id}';"]
            subscribe = dict(Subscribe=dict(request_id=1, query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)
            
            for row in self._receive_websocket_subscription_data("fetch_claim_membership_id_by_user_id"):
                claim_id = row.get("claim_entity_id")
                if claim_id:
                    logging.info(f"Claim ID for user {user_id} found: {claim_id}")
                    return claim_id
            
            logging.error(f"Claim ID for user {user_id} not found")
            return None

    def fetch_claim_state(self, claim_id: str) -> dict | None:
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            
            if not claim_id:
                raise ValueError("Claim ID is missing.")
            
            sanitized_claim_id = str(claim_id).replace("'", "''")

            query_strings = [f"SELECT * FROM claim_state WHERE entity_id = '{sanitized_claim_id}';"]
            subscribe = dict(Subscribe=dict(request_id=1, query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)

            for row in self._receive_websocket_subscription_data("fetch_claim_state"):
                claim_data = {
                    "claim_id": row.get("entity_id"),
                    "owner_id": row.get("owner_player_entity_id"),
                    "owner_building_id": row.get("owner_building_entity_id"),
                    "claim_name": row.get("name"),
                }
                logging.info(f"Claim state for claim ID {claim_id} found.")
                return claim_data
            
            logging.error(f"Claim data for claim ID {claim_id} not found")
            return None

    def fetch_claim_local_state(self, claim_id: str) -> dict | None:
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            
            if not claim_id:
                raise ValueError("Claim ID is missing.")
            
            
            sanitized_claim_id = str(claim_id).replace("'", "''")

            query_strings = [f"SELECT * FROM claim_local_state WHERE entity_id = '{sanitized_claim_id}';"]
            subscribe = dict(Subscribe=dict(request_id=1, query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)
            
            for row in self._receive_websocket_subscription_data("fetch_claim_local_state"):
                collected_data = {
                    "claim_id": row.get("entity_id"),
                    "building_maintenance": row.get("building_maintenance"),
                    "num_tiles": row.get("num_tiles"),
                    "num_tile_neighbors": row.get("num_tile_neighbors"),
                    "treasury": row.get("treasury"),
                    "xp_gained_since_last_coin_minting": row.get("xp_gained_since_last_coin_minting"),
                    "supplies_purchase_threshold": row.get("supplies_purchase_threshold"),
                    "supplies_purchase_price": row.get("supplies_purchase_price"),
                    "building_description_id": row.get("building_description_id"),
                }
                logging.info(f"Claim local state for claim ID {claim_id} found.")
                return collected_data
            
            logging.error(f"Claim local state for claim ID {claim_id} not found")
            return None
        

    def fetch_claim_building_state(self, claim_id: str) -> list[dict] | None:
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            
            if not claim_id:
                raise ValueError("Claim ID is missing.")
            
            try:
                int_claim_id = int(claim_id)
            except ValueError:
                raise ValueError(f"Invalid claim ID format: {claim_id}. Expected an integer.")

            query_strings = [f"select * from building_state where claim_entity_id = {int_claim_id};"]
            subscribe = dict(Subscribe=dict(request_id=1, query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)
            
            building_states = []
            for row in self._receive_websocket_subscription_data("fetch_claim_building_state"):
                building_states.append(row)
            
            if building_states:
                logging.info(f"Building states found for claim ID {claim_id}.")
                return building_states
            else:
                logging.error(f"No building states found for claim ID {claim_id}")
                return []

    def fetch_building_description(self, building_id: str | int) -> dict | None:
        if not self.ws_connection:
            logging.warning("WebSocket connection not established, but fetching building description from local file.")
        
        if not building_id:
            raise ValueError("Building ID is missing.")
        
        if self._building_desc is None:
            self._building_desc = self._load_reference_data('building_desc.json')
            if self._building_desc is None:
                return None 
        
        selected_building = next((b for b in self._building_desc if str(b.get('id')) == str(building_id)), None)
        if selected_building:
            logging.debug(f"Building description for ID {building_id} found.")
            return selected_building

        logging.error(f"Building description for building ID {building_id} not found")
        return None

    def fetch_building_type_id(self, build_description_id: str | int) -> str | int | None:
        if not self.ws_connection:
            logging.warning("WebSocket connection not established, but fetching building type ID from local file.")
        
        if not build_description_id:
            raise ValueError("Building description ID is missing.")
        
        if self._building_function_type_mapping_desc is None:
            self._building_function_type_mapping_desc = self._load_reference_data('building_function_type_mapping_desc.json')
            if self._building_function_type_mapping_desc is None:
                return None 
        
        selected_type = next((b for b in self._building_function_type_mapping_desc 
                              if str(build_description_id) in [str(d_id) for d_id in b.get('desc_ids', [])]), None)
        
        if selected_type:
            type_id = selected_type.get('type_id')
            logging.debug(f"Building type ID for description ID {build_description_id} found: {type_id}")
            return type_id

        logging.error(f"Building type for building description ID {build_description_id} not found")
        return None

    def fetch_building_type_description(self, type_id: str | int) -> dict | None:
        if not self.ws_connection:
            logging.warning("WebSocket connection not established, but fetching building type description from local file.")
        
        if not type_id:
            raise ValueError("Type ID is missing.")
        
        if self._building_type_desc is None:
            self._building_type_desc = self._load_reference_data('building_type_desc.json')
            if self._building_type_desc is None:
                return None 
        
        selected_type = next((b for b in self._building_type_desc if b.get('id') == int(type_id)), None)
        if selected_type:
            logging.debug(f"Building type description for type ID {type_id} found.")
            return selected_type

        logging.error(f"Building type description for type ID {type_id} not found")
        return None

    def fetch_claim_member_state(self, claim_id: str) -> list[dict] | None:
        """
        Fetches claim member state for a given claim ID.
        Returns a list of claim members with their entity IDs and usernames.
        """
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            
            if not claim_id:
                raise ValueError("Claim ID is missing.")
            
            sanitized_claim_id = str(claim_id).replace("'", "''")
            
            query_strings = [f"SELECT * FROM claim_member_state WHERE claim_entity_id = '{sanitized_claim_id}';"]
            subscribe = dict(Subscribe=dict(request_id=1, query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)
            
            members = []
            for row in self._receive_websocket_subscription_data("fetch_claim_member_state"):
                member_data = {
                    "entity_id": row.get("entity_id"),
                    "claim_entity_id": row.get("claim_entity_id"),
                    "player_entity_id": row.get("player_entity_id"),
                    "user_name": row.get("user_name"),
                    "inventory_permission": row.get("inventory_permission"),
                    "build_permission": row.get("build_permission"),
                    "officer_permission": row.get("officer_permission"),
                    "co_owner_permission": row.get("co_owner_permission")
                }
                members.append(member_data)
            
            if members:
                logging.info(f"Found {len(members)} claim members for claim ID {claim_id}")
                return members
            else:
                logging.info(f"No claim members found for claim ID {claim_id}")
                return []

    def fetch_user_by_player_entity_id(self, player_entity_id: str) -> dict | None:
        """
        Fetches user information for a given player entity ID.
        Returns user data with user_name if found.
        """
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            
            if not player_entity_id:
                raise ValueError("Player entity ID is missing.")
            
            sanitized_player_id = str(player_entity_id).replace("'", "''")
            
            query_strings = [f"SELECT * FROM claim_member_state WHERE player_entity_id = '{sanitized_player_id}';"]
            subscribe = dict(Subscribe=dict(request_id=1, query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)
            
            for row in self._receive_websocket_subscription_data("fetch_user_by_player_entity_id"):
                user_data = {
                    "entity_id": row.get("entity_id"),
                    "player_entity_id": row.get("player_entity_id"),
                    "user_name": row.get("user_name"),
                    "claim_entity_id": row.get("claim_entity_id")
                }
                if user_data.get("user_name"):
                    logging.debug(f"Found user data for player {player_entity_id}: {user_data.get('user_name')}")
                    return user_data
            
            logging.debug(f"No user data found for player entity ID {player_entity_id}")
            return None

    def fetch_inventory_state(self, entity_id: str) -> dict | None:
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            
            if not entity_id:
                raise ValueError("Entity ID is missing.")
            
            sanitized_entity_id = str(entity_id).replace("'", "''")

            query_strings = [f"SELECT * FROM inventory_state WHERE owner_entity_id = '{sanitized_entity_id}';"]
            subscribe = dict(Subscribe=dict(request_id=1, query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)
            
            for row in self._receive_websocket_subscription_data("fetch_inventory_state"):
                logging.info(f"Inventory state for entity ID {entity_id} found.")
                return row
            
            logging.error(f"Inventory state for entity ID {entity_id} not found")
            return None

    def fetch_claim_supplies(self, claim_id: str) -> dict | None:
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            
            if not claim_id:
                raise ValueError("Claim ID is missing.")
            
            sanitized_claim_id = claim_id.replace("'", "''")
            
            query_strings = [f"SELECT * FROM claim_local_state WHERE entity_id = '{sanitized_claim_id}';"]
            subscribe = dict(Subscribe=dict(request_id=1,query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)
            
            for row in self._receive_websocket_subscription_data("fetch_claim_supplies"):
                collected_data = {
                    "claim_id": row.get("entity_id"),
                    "supplies": row.get('supplies'),
                    "num_tiles": row.get('num_tiles'),
                    "treasury": row.get('treasury'),
                }
                logging.info(f"Claim supplies for claim ID {claim_id} found.")
                return collected_data
            
            logging.error(f"Claim supplies for claim ID {claim_id} not found")
            return None
    
    def fetch_building_nickname_state(self) -> list[dict] | None:
        """
        Fetches all rows from the building_nickname_state table via WebSocket.
        Returns a list of dictionaries, each representing a row.
        """
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")

            query_strings = ["SELECT * FROM building_nickname_state;"]
            subscribe = dict(Subscribe=dict(request_id=1, query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)

            results = []
            for row in self._receive_websocket_subscription_data("fetch_building_nickname_state"):
                results.append(row)

            if results:
                logging.info(f"Fetched {len(results)} rows from building_nickname_state.")
                return results
            else:
                logging.error("No rows found in building_nickname_state.")
                return []

    def fetch_passive_craft_state(self, entity_ids: list[str]) -> list[dict] | None:
        """
        Fetches passive craft state for multiple entity IDs from the passive_craft_state table via WebSocket.
        Uses individual queries for each entity ID to avoid database constraint issues.
        
        Args:
            entity_ids: List of entity IDs to query passive craft state for
            
        Returns:
            List of dictionaries representing passive craft state rows, or empty list if none found.
        """
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")

            if not entity_ids:
                logging.warning("No entity IDs provided for passive craft state query")
                return []

            # Sanitize entity IDs
            sanitized_ids = [str(int(entity_id)) for entity_id in entity_ids if str(entity_id).isdigit()]
            
            if not sanitized_ids:
                logging.warning("No valid entity IDs provided for passive craft state query")
                return []
            
            # Query each entity ID individually to avoid database constraints
            query_strings = [f"SELECT * FROM passive_craft_state WHERE building_entity_id = '{entity_id}';" for entity_id in sanitized_ids]
            
            logging.info(f"Executing passive craft state queries for {len(sanitized_ids)} buildings")
            logging.info(f"Sample queries: {query_strings[:3]}")
            
            subscribe = dict(Subscribe=dict(request_id=1, query_strings=query_strings))
            sub = json.dumps(subscribe)
            self.ws_connection.send(sub)

            results = []
            for row in self._receive_websocket_subscription_data("fetch_passive_craft_state"):
                results.append(row)

            logging.info(f"Fetched {len(results)} rows from passive_craft_state for {len(sanitized_ids)} entity IDs.")
            if results:
                logging.info(f"Sample result: {results[0]}")
            return results

    def logout(self):
        """
        Clears stored credentials from keyring and resets instance properties.
        """
        try:
            self._delete_credential_from_keyring('authorization_token')
            self._delete_credential_from_keyring('email')
            self.auth = None
            self.email = None
            logging.info("Successfully logged out. All credentials cleared.")
            return True
        except Exception as e:
            logging.error(f"Error during logout: {e}")
            return False
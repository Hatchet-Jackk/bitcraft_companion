import json
import logging
import os
import re
import sqlite3
import sys
import threading
import uuid
import time

import keyring
import requests
from websockets import Subprotocol
from websockets.sync.client import connect


class BitCraft:
    """BitCraft API client for WebSocket database queries and authentication."""

    SERVICE_NAME = "BitCraftAPI"
    DEFAULT_SUBPROTOCOL = "v1.json.spacetimedb"
    AUTH_API_BASE_URL = "https://api.bitcraftonline.com/authentication"

    def _get_data_directory(self):
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(__file__)

    def __init__(self):
        self.host = os.getenv("BITCRAFT_SPACETIME_HOST", "bitcraft-early-access.spacetimedb.com")
        self.uri = "{scheme}://{host}/v1/database/{module}/{endpoint}"
        self.proto = Subprotocol(self.DEFAULT_SUBPROTOCOL)
        self.ws_connection = None
        self.module = None
        self.endpoint = None
        self.ws_uri = None
        self.headers = {}
        self.ws_lock = threading.Lock()
        self.subscription_thread = None
        self._stop_subscription = threading.Event()

        self._building_desc = None
        self._building_function_type_mapping_desc = None
        self._building_type_desc = None

        self.load_user_data_from_file()
        self.email = self._get_credential_from_keyring("email")
        self.auth = self._get_credential_from_keyring("authorization_token")

    # ... (all your existing methods like _get_credential_from_keyring, authenticate, etc. remain unchanged)
    def _get_credential_from_keyring(self, key_name: str) -> str | None:
        try:
            credential = keyring.get_password(self.SERVICE_NAME, key_name)
            if credential:
                logging.debug(f"Credential '{key_name}' loaded from keyring.")
            else:
                logging.debug(f"Credential '{key_name}' not found in keyring.")
            return credential
        except keyring.errors.NoKeyringError:
            logging.warning("No keyring backend found. Credentials will not be securely stored.")
            return None
        except Exception as e:
            logging.error(f"Error retrieving '{key_name}' from keyring: {e}")
            return None

    def _set_credential_in_keyring(self, key_name: str, value: str):
        try:
            keyring.set_password(self.SERVICE_NAME, key_name, value)
            logging.debug(f"Credential '{key_name}' stored in keyring.")
        except keyring.errors.NoKeyringError:
            logging.warning("No keyring backend found. Cannot securely store credentials.")
        except Exception as e:
            logging.error(f"Error storing '{key_name}' in keyring: {e}")

    def _delete_credential_from_keyring(self, key_name: str):
        try:
            keyring.delete_password(self.SERVICE_NAME, key_name)
            logging.debug(f"Credential '{key_name}' deleted from keyring.")
        except keyring.errors.NoKeyringError:
            logging.warning("No keyring backend found. Cannot delete credentials.")
        except keyring.errors.PasswordDeleteError:
            logging.warning(f"Credential '{key_name}' not found in keyring to delete.")
        except Exception as e:
            logging.error(f"Error deleting '{key_name}' from keyring: {e}")

    def _load_reference_data(self, table: str) -> list[dict] | None:
        if table == "player_data":
            file_path = os.path.join(self._get_data_directory(), "player_data.json")
            try:
                with open(file_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading player_data.json: {e}")
                return None

        db_path = os.path.join(os.path.dirname(__file__), "data", "data.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            json_fields_map = {
                "resource_desc": ["on_destroy_yield", "footprint", "rarity", "enemy_params_id"],
                "item_desc": ["rarity"],
                "cargo_desc": ["on_destroy_yield_cargos", "rarity"],
                "building_desc": ["functions", "footprint", "build_permission", "interact_permission"],
                "type_desc_ids": ["desc_ids"],
                "building_types": ["category", "actions"],
            }
            json_fields = json_fields_map.get(table, [])
            for row in result:
                for field in json_fields:
                    if field in row and row[field] is not None:
                        try:
                            row[field] = json.loads(row[field])
                        except Exception:
                            pass
            conn.close()
            return result
        except Exception as e:
            logging.error(f"Error loading reference data from DB for table {table}: {e}")
            return None

    def update_user_data_file(self, key: str, value: str):
        file_path = os.path.join(self._get_data_directory(), "player_data.json")
        data = {}
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            logging.warning("player_data.json not found. Creating a new one.")
        except json.JSONDecodeError:
            logging.warning("player_data.json is malformed. Overwriting with new data.")
            data = {}

        try:
            data[key] = value
            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)
            logging.info(f"User data file updated: {key} in {file_path}")
        except Exception as e:
            logging.error(f"Error writing to player_data.json: {e}")

    def load_user_data_from_file(self):
        try:
            with open(os.path.join(self._get_data_directory(), "player_data.json"), "r") as f:
                data = json.load(f)
                self.email = data.get("email")
                self.region = data.get("region")
                self.player_name = data.get("player_name")
                self.host = data.get("host", self.host)
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
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(email_regex, email) is not None

    def get_access_code(self, email: str) -> bool:
        if not email:
            raise ValueError("Email is required to request an access code.")
        if not self._is_valid_email(email):
            raise ValueError(f"Invalid email format: {email}")
        logging.info(f"Requesting new access code for {email}...")
        encoded_email = requests.utils.quote(email)
        uri = f"{self.AUTH_API_BASE_URL}/request-access-code?email={encoded_email}"
        try:
            response = requests.post(uri)
            response.raise_for_status()
            logging.info("Access Code request was successful! Check your email for the code.")
            return True
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error requesting access code: {http_err} - {response.text}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Network error requesting access code: {req_err}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during access code request: {e}")
        return False

    def get_authorization_token(self, email: str, access_code: str) -> str | None:
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
            self._set_credential_in_keyring("authorization_token", f"Bearer {authorization_token}")
            self._set_credential_in_keyring("email", email)
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
        return None

    def authenticate(self, email: str = None, access_code: str = None) -> bool:
        effective_email = email if email is not None else self.email
        if not effective_email:
            logging.error("Authentication failed: Email is required.")
            return False
        if not self._is_valid_email(effective_email):
            logging.error(f"Authentication failed: Invalid email format: {effective_email}")
            return False
        if self.auth and access_code is None:
            logging.info("Authorization token already exists. Assuming authenticated.")
            return True
        if not access_code:
            logging.error("Authentication failed: Access code is required to obtain a new authorization token.")
            return False
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
        self.update_user_data_file("host", host)
        logging.info(f"Host set: {host}")

    def set_auth(self, auth: str, email: str = None):
        if not auth:
            raise ValueError("Auth token cannot be empty")
        self.auth = auth
        self._set_credential_in_keyring("authorization_token", auth)
        if email:
            self.email = email
            self._set_credential_in_keyring("email", email)
        logging.info(f"Auth token set: {auth[:15]}...")
        if email:
            logging.info(f"Email stored: {email}")

    def set_region(self, region: str):
        if not region:
            raise ValueError("Region cannot be empty")
        self.module = region
        self.update_user_data_file("region", region)
        logging.info(f"Region set: {region}")

    def set_endpoint(self, endpoint: str = "subscribe"):
        if not endpoint:
            raise ValueError("Endpoint cannot be empty")
        self.endpoint = endpoint
        logging.info(f"Endpoint set: {endpoint}")

    def set_websocket_uri(self):
        if not self.host or not self.module or not self.endpoint:
            raise ValueError("Host, module, and endpoint must be set before building WebSocket URI.")
        if not self.auth:
            raise RuntimeError("Authorization token is not set. Authenticate first.")
        self.ws_uri = self.uri.format(scheme="wss", host=self.host, module=self.module, endpoint=self.endpoint)
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
                    max_queue=None,
                )
                first_msg = self.ws_connection.recv()
                logging.info(f"Initial WebSocket handshake message: {first_msg[:20]}...")
                logging.info("WebSocket connection established")
            except Exception as e:
                logging.error(f"Failed to establish WebSocket connection: {e}")
                self.ws_connection = None
                raise

    def close_websocket(self):
        with self.ws_lock:
            self._stop_subscription.set()  # Signal subscription thread to stop
            if self.subscription_thread and self.subscription_thread.is_alive():
                self.subscription_thread.join()  # Wait for thread to finish

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

    def _receive_one_off_query(self, query_name: str):
        if not self.ws_connection:
            raise RuntimeError("WebSocket connection is not established")
        for msg in self.ws_connection:
            try:
                data = json.loads(msg)
                if "OneOffQueryResponse" in data:
                    tables = data["OneOffQueryResponse"].get("tables", [])
                    for table in tables:
                        for row in table.get("rows", []):
                            try:
                                yield json.loads(row)
                            except json.JSONDecodeError:
                                logging.error(f"Failed to decode JSON from WebSocket row: {str(row)[:100]}...")
                                continue
                    break  # Exit after processing the one-off response
                elif "error" in data:
                    logging.error(f"WebSocket error received for {query_name}: {data['error']}")
                    return
            except json.JSONDecodeError:
                logging.error(f"Failed to decode JSON from WebSocket message: {msg[:100]}...")
            except Exception as e:
                logging.error(f"Unexpected error processing WebSocket message: {e}")
        return

    def _listen_for_subscription_updates(self, callback):
        """A dedicated loop for listening to subscription messages."""
        logging.info("Subscription listener thread started.")
        try:
            while not self._stop_subscription.is_set():
                if not self.ws_connection:
                    logging.warning("Subscription listener: WebSocket connection is closed.")
                    break
                try:
                    # Use a timeout to allow the loop to check the stop event
                    msg = self.ws_connection.recv(timeout=1.0)
                    data = json.loads(msg)
                    # This is a simplified parser. You'll need to adapt it to your actual message format.
                    if "SubscriptionUpdate" in data:
                        callback(data)  # Pass the raw update to the callback
                except TimeoutError:
                    continue  # No message received, loop again
                except json.JSONDecodeError:
                    logging.error(f"Failed to decode JSON from subscription message: {msg[:100]}...")
                except Exception as e:
                    # Handle connection drops or other errors
                    logging.error(f"Error in subscription listener: {e}")
                    break
        finally:
            logging.info("Subscription listener thread stopped.")

    def start_subscription_listener(self, queries: list[str], callback: callable):
        """Sends subscription queries and starts a listener thread."""
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established.")

            self._stop_subscription.clear()

            # Send all subscription queries
            for query_string in queries:
                subscribe_message = {
                    "Subscribe": {"message_id": str(uuid.uuid4()).replace("-", ""), "query_string": query_string}
                }
                self.ws_connection.send(json.dumps(subscribe_message))
                logging.info(f"Sent subscription request: {query_string}")
                # We need to consume the initial response for each subscription
                initial_response = self.ws_connection.recv()
                logging.debug(f"Initial subscription response: {initial_response[:100]}...")

            # Start the listener thread
            self.subscription_thread = threading.Thread(
                target=self._listen_for_subscription_updates, args=(callback,), daemon=True
            )
            self.subscription_thread.start()

    # --- Your existing fetch methods (fetch_user_id, etc.) ---
    # These will now use _receive_one_off_query
    def fetch_user_id(self, username: str) -> str | None:
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            sanitized_username = username.lower().replace("'", "''")
            query_string = f"SELECT * FROM player_lowercase_username_state WHERE username_lowercase = '{sanitized_username}';"
            subscribe = dict(OneOffQuery=dict(message_id=str(uuid.uuid4()).replace("-", ""), query_string=query_string))
            self.ws_connection.send(json.dumps(subscribe))
            for row in self._receive_one_off_query("fetch_user_id"):
                user_id = row.get("entity_id")
                if user_id:
                    logging.info(f"User ID for {username} found: {user_id}")
                    return user_id
            logging.error(f"User ID for {username} not found")
            return None

    def fetch_claim_membership_id_by_user_id(self, user_id: str) -> str | None:
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            if not user_id:
                raise ValueError("User ID missing.")
            sanitized_user_id = str(user_id).replace("'", "''")
            query_string = f"SELECT * FROM claim_member_state WHERE player_entity_id = '{sanitized_user_id}';"
            subscribe = dict(OneOffQuery=dict(message_id=str(uuid.uuid4()).replace("-", ""), query_string=query_string))
            self.ws_connection.send(json.dumps(subscribe))
            for row in self._receive_one_off_query("fetch_claim_membership_id_by_user_id"):
                claim_id = row.get("claim_entity_id")
                if claim_id:
                    logging.info(f"Claim ID for user {user_id} found: {claim_id}")
                    return claim_id
            logging.error(f"Claim ID for user {user_id} not found")
            return None

    # ... (adapt all other fetch_* methods similarly to use _receive_one_off_query) ...
    def fetch_claim_state(self, claim_id: str) -> dict | None:
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")
            if not claim_id:
                raise ValueError("Claim ID is missing.")
            sanitized_claim_id = str(claim_id).replace("'", "''")
            query_string = f"SELECT * FROM claim_state WHERE entity_id = '{sanitized_claim_id}';"
            subscribe = dict(OneOffQuery=dict(message_id=str(uuid.uuid4()).replace("-", ""), query_string=query_string))
            self.ws_connection.send(json.dumps(subscribe))
            for row in self._receive_one_off_query("fetch_claim_state"):
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

    def logout(self):
        try:
            self.close_websocket()  # Ensure connection and listener are stopped
            self._delete_credential_from_keyring("authorization_token")
            self._delete_credential_from_keyring("email")
            self.auth = None
            self.email = None
            logging.info("Successfully logged out. All credentials cleared.")
            return True
        except Exception as e:
            logging.error(f"Error during logout: {e}")
            return False

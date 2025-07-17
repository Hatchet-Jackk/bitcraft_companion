import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class Player:
    def __init__(self, username):
        self.username = username
        self.user_id = None
        self.claim_id = None
        self.inventory = {}

    def username(self):
        logging.info(f"Fetching username: {self.username}")
        return self.username
    
    def set_inventory(self, inventory):
        logging.info(f"Inventory set to: {inventory}")
        pass

    def get_inventory(self):
        logging.info(f"Fetching inventory: {self.inventory}")
        return self.inventory
    
    def set_user_id(self, user_id):
        logging.info(f"User ID set to: {user_id}")
        self.user_id = user_id
    
    def get_user_id(self):
        logging.info(f"Fetching user ID: {self.user_id}")
        return self.user_id

    def set_claim_id(self, claim_id):
        logging.info(f"Claim ID set to: {claim_id}")
        self.claim_id = claim_id

    def get_claim_id(self):
        logging.info(f"Fetching claim ID: {self.claim_id}")
        return self.claim_id
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "testpassword123"
ADMIN_NAME = "Admin"

TEST_USERS: List[Tuple[str, str, str]] = [
    ("user1@test.com", "testpassword123", "User One"),
    ("user2@test.com", "testpassword123", "User Two"),
]


async def setup_users(client):
    """Ensure admin and test users exist."""
    logger.info("Preparing admin: %s", ADMIN_EMAIL)
    try:
        await client.signin(email=ADMIN_EMAIL, password=ADMIN_PASSWORD)
        logger.info("Admin already exists, signed in")
    except RuntimeError:
        await client.signup(email=ADMIN_EMAIL, password=ADMIN_PASSWORD, name=ADMIN_NAME)
        logger.info("Admin created and signed in")

    admin_token = client.token

    for email, password, name in TEST_USERS:
        logger.info("Preparing user: %s", email)
        client.token = None  # Clear token to try signin as new user
        try:
            await client.signin(email=email, password=password)
            logger.info("User %s already exists", email)
        except RuntimeError:
            client.token = admin_token  # Use admin token to create user
            try:
                await client.admin_create_user(name=name, email=email, password=password)
                logger.info("User %s created by admin", email)
            except RuntimeError as e:
                logger.error("Failed to create user %s: %s", email, e)

        client.token = admin_token  # Restore admin token for next operations

    return {
        "admin": {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        "users": [{"email": u[0], "password": u[1]} for u in TEST_USERS],
    }

import os
import sys
from alembic.config import Config
from alembic import command
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("upgrade_db")

def upgrade():
    # Make sure we are in the correct directory
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)
    
    logger.info("Starting database upgrade...")
    
    alembic_cfg = Config("alembic.ini")
    
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("Database upgrade completed successfully!")
    except Exception as e:
        logger.error(f"Error during upgrade: {e}")
        
        # If it fails because tables already exist, we can stamp the db
        if "already exists" in str(e).lower():
            logger.warning("Tables already exist. Stamping database to head...")
            try:
                command.stamp(alembic_cfg, "head")
                logger.info("Database stamped successfully! Alembic is now in sync.")
            except Exception as stamp_err:
                logger.error(f"Failed to stamp database: {stamp_err}")

if __name__ == "__main__":
    upgrade()

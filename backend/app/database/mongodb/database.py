from app.database.mongodb.connection import db_connection


def get_database():
    """
    Dependency provider for Motor database instance.
    """
    return db_connection.db

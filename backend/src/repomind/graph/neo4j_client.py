from neo4j import Driver, GraphDatabase

from repomind.config import Settings, get_settings


def get_driver(settings: Settings | None = None) -> Driver:
    settings = settings or get_settings()
    return GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))

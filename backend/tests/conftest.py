import pytest
from neo4j.exceptions import ServiceUnavailable

from repomind.config import Settings
from repomind.graph import GraphWriter, get_driver

_TEST_SETTINGS = Settings(neo4j_uri="bolt://localhost:7687", neo4j_user="neo4j", neo4j_password="repomind-dev")


@pytest.fixture(scope="session")
def neo4j_driver():
    driver = get_driver(_TEST_SETTINGS)
    try:
        driver.verify_connectivity()
    except ServiceUnavailable:
        pytest.skip("Neo4j is not reachable at bolt://localhost:7687 -- start it to run graph tests")
    yield driver
    driver.close()


@pytest.fixture
def graph_writer(neo4j_driver):
    writer = GraphWriter(neo4j_driver)
    writer.clear()
    yield writer
    writer.clear()

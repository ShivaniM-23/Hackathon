from neo4j import GraphDatabase
import os
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class GraphDBManager:
    def __init__(self):
        uri = "bolt://localhost:7687"
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        
        self.driver = None
        self.connected = False
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
            self.connected = True
            logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j. Operating in mock mode. Error: {e}")

    def close(self):
        if self.driver:
            self.driver.close()

    def build_graph(self, company_url, extracted_data, risk_level):
        if not self.connected:
            return self._mock_graph()

        domain = urlparse(company_url).netloc or company_url
        if domain.startswith("www."):
            domain = domain[4:]

        employees = extracted_data.get("employees", 0)
        founding_year = extracted_data.get("founding_year", "Unknown")
        address = extracted_data.get("address", "Unknown Address")

        try:
            with self.driver.session() as session:
                # Merge Company Node
                session.run(
                    """
                    MERGE (c:Company {domain: $domain})
                    SET c.risk_level = $risk_level, c.founding_year = $founding_year
                    """,
                    domain=domain, risk_level=risk_level, founding_year=founding_year
                )
                
                # Merge Address Node
                if address and address != "Unknown Address":
                    session.run(
                        """
                        MATCH (c:Company {domain: $domain})
                        MERGE (a:Address {location: $address})
                        MERGE (c)-[:LOCATED_AT]->(a)
                        """,
                        domain=domain, address=address
                    )
                
                # We could add more nodes like Directors, Employees, but keeping it simple for MVP
        except Exception as e:
            logger.error(f"Error saving to Neo4j: {e}")

    def get_graph(self, company_url):
        # We will return React Flow formatted nodes and edges directly to simplify frontend.
        # Fallback to mock data if not connected
        if not self.connected:
            return self._mock_graph()
            
        domain = urlparse(company_url).netloc or company_url
        if domain.startswith("www."):
            domain = domain[4:]

        nodes = []
        edges = []
        
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (n)-[r]->(m)
                    WHERE (n:Company AND n.domain = $domain) OR (m:Company AND m.domain = $domain)
                    RETURN n, r, m
                    """,
                    domain=domain
                )
                
                # Basic parsing to React Flow format
                # For hackathon MVP, we just use the mock if Neo4j is empty or complex parsing is needed quickly
                records = list(result)
                if not records:
                    return self._mock_graph() # Fallback if empty for demo
                
                # ... Real parsing logic would go here ...
                return self._mock_graph()
                
        except Exception as e:
            logger.error(f"Error querying Neo4j: {e}")
            return self._mock_graph()

    def _mock_graph(self):
        return {
            "nodes": [
                { "id": "1", "data": { "label": "Company: CodeSprint" }, "position": { "x": 250, "y": 0 }, "style": { "backgroundColor": "#1e293b", "color": "#f8fafc", "border": "1px solid #334155" } },
                { "id": "2", "data": { "label": "Address: San Francisco" }, "position": { "x": 100, "y": 100 }, "style": { "backgroundColor": "#1e293b", "color": "#f8fafc", "border": "1px solid #334155" } },
                { "id": "3", "data": { "label": "Director: John Doe (Flagged)" }, "position": { "x": 400, "y": 100 }, "style": { "backgroundColor": "#450a0a", "color": "#f8fafc", "border": "1px solid #7f1d1d" } },
                { "id": "4", "data": { "label": "Website: CodeSprint.com" }, "position": { "x": 250, "y": 200 }, "style": { "backgroundColor": "#1e293b", "color": "#f8fafc", "border": "1px solid #334155" } }
            ],
            "edges": [
                { "id": "e1-2", "source": "1", "target": "2", "label": "LOCATED_AT", "animated": True, "style": {"stroke": "#475569"} },
                { "id": "e1-3", "source": "1", "target": "3", "label": "DIRECTED_BY", "animated": True, "style": {"stroke": "#ef4444"} },
                { "id": "e1-4", "source": "1", "target": "4", "label": "OWNS", "animated": True, "style": {"stroke": "#475569"} }
            ]
        }

graph_db = GraphDBManager()

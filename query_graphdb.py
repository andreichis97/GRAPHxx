from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery

# Configure the GraphDB connection details
endpoint = "http://localhost:7200/repositories/test"

# Create a Graph instance
graph = Graph()

# Set up the GraphDB as a SPARQL endpoint
graph.open(endpoint)

# Define the SPARQL query
query = """
PREFIX : <http://example.org/#>
SELECT ?subject ?predicate ?object
WHERE {
  ?subject ?predicate ?object .
}
LIMIT 10
"""

# Prepare the query
prepared_query = prepareQuery(query)

# Execute the query and retrieve the results
results = graph.query(prepared_query)

#print(results)
# Process and print the query results
for row in results:
    subject = row['subject']
    predicate = row['predicate']
    obj = row['object']
    print(f"Subject: {subject}")
    print(f"Predicate: {predicate}")
    print(f"Object: {obj}")
    print("---")

# Close the GraphDB connection
graph.close()

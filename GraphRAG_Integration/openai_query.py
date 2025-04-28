from SPARQLWrapper import SPARQLWrapper, JSON

readFile = open("D://Andrei//ModellingTools//Graph_Modelling_Tool//Scripts//chat_gpt_query_prompt.txt", "r")
writeFile = open("D://Andrei//ModellingTools//Graph_Modelling_Tool//Scripts//openai_query_results.txt", "w")
fileContent = readFile.readlines()

prompt = '"'
repositoryName = fileContent[0].strip()
prompt = prompt + fileContent[2].strip()
prompt = prompt + '"'

print(prompt)
print(repositoryName)

# Set the endpoint URL of the graph database server
endpoint_url = f"""http://localhost:7200/repositories/{repositoryName}"""
#endpoint_url = endpoint_url.rstrip()

# Create a new SPARQLWrapper instance
sparql = SPARQLWrapper(endpoint_url)

# Set the SPARQL query
query = """
PREFIX : <http://www.example.org#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX helper: <http://www.ontotext.com/helper/>
PREFIX gpt: <http://www.ontotext.com/gpt/>

SELECT ?answer
WHERE
{
    {
        SELECT (helper:rdf(helper:tuple(?s, ?p, ?o)) AS ?rdf) WHERE
		{
			{
			?s ?p ?o
            }
		}
    }
                ?answer gpt:ask (""" + prompt + """ ?rdf)
}"""

print(endpoint_url)
print(query)
# Set the SPARQL query type to SELECT
#sparql.setQueryType("SELECT")
#sparql.queryType("SELECT")

# Set the SPARQL query
sparql.setQuery(query)

# Set the output format to JSON
sparql.setReturnFormat(JSON)

# Execute the query and store the results
results = sparql.query().convert()

# Loop through the results and print them
for result in results["results"]["bindings"]:
    answer = result["answer"]["value"]
    #print(f"{answer}")
    writeFile.write(f"{answer}")

readFile.close()
writeFile.close()

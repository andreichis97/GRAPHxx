from apikey import apiKey
import os
from SPARQLWrapper import SPARQLWrapper, RDF, TURTLE
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import rdflib

os.environ['OPENAI_API_KEY'] = apiKey

readFile = open("D://Andrei//ModellingTools//Graph_Modelling_Tool//Scripts//chat_gpt_query_prompt.txt", "r")
writeFile = open("D://Andrei//ModellingTools//Graph_Modelling_Tool//Scripts//openai_query_results.txt", "w")
fileContent = readFile.readlines()

subjectLlm = ChatOpenAI(model='gpt-4-1106-preview', temperature=0)

user_input_placeholder = '"'
repositoryName = fileContent[0].strip()
user_input_placeholder = user_input_placeholder + fileContent[2].strip()
user_input_placeholder = user_input_placeholder + '"'

subjectTemplate = PromptTemplate(
    input_variables = ['user_input_placeholder'],
    template = 'Identify the subject of the prompt {user_input_placeholder}. When providing the response write strictly the subject without other comments or details. For example, if the prompt is: Give me information about Jane Doe, the returned result should be Jane Doe. If the prompt is: Which companies would be affected in case AceTech goes bankrupt?, the returned result should be AceTech'
)
subjectChain = LLMChain(llm=subjectLlm, prompt=subjectTemplate, verbose=True)
subject = subjectChain.run(user_input_placeholder = user_input_placeholder)

print("SUBJECT of Query:")
print(subject)

print(user_input_placeholder)
print(repositoryName)

# Set the endpoint URL of the graph database server
endpointUrl = f"""http://localhost:7200/repositories/{repositoryName}"""
#endpoint_url = endpoint_url.rstrip()

# Create a new SPARQLWrapper instance
sparql = SPARQLWrapper(endpointUrl)

query = """
SELECT *
WHERE
{
    ?s ?p ?o .
}
"""

queryWithSubject = """
    PREFIX : <http://www.example.org#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX schema: <http://schema.org/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    DESCRIBE ?x
    WHERE
    {
        {
            ?x :hasLabel ?name
            FILTER REGEX(?name ,""" + '"' + subject + '"' + """, "i")
        }
    }
    """

queryWithSubjectV2 = """
PREFIX : <http://www.example.org#>
CONSTRUCT 
{
    ?lookingFor ?relation1 ?ob.
    ?ob ?relation2 ?otherOb.
    ?otherOb ?relation3 ?ob.
    ?ob ?relation4 ?lookingFor.
    ?otherOb ?relation5 ?otherOtherOb.
    ?previousOb ?relation6 ?otherOb.
}
WHERE
{
    {
    	?lookingFor :hasLabel """ + "'" + subject + "'" + """; 
    		?relation1 ?ob. 
    	?ob ?relation2 ?otherOb.
	}
    UNION
    {
    	?lookingFor :hasLabel """ + "'" + subject + "'" + """; 
    		?relation1 ?ob. 
    	?ob ?relation2 ?otherOb.
    	?otherOb ?relation5 ?otherOtherOb.
    }
    UNION
    {
    	?otherOb ?relation3 ?ob. 
    	?ob ?relation4 ?lookingFor.
    	?lookingFor :hasLabel """ + "'" + subject + "'" + """. 
	}
    UNION
    {
    	?previousOb ?relation6 ?otherOb.
        ?otherOb ?relation3 ?ob. 
    	?ob ?relation4 ?lookingFor.
    	?lookingFor :hasLabel """ + "'" + subject + "'" + """. 
    }
}
"""
g = rdflib.Graph()
print(queryWithSubjectV2)
sparql.setQuery(queryWithSubjectV2)
sparql.setReturnFormat(TURTLE)
graph_context_as_Turtle = sparql.queryAndConvert()
g.parse(graph_context_as_Turtle, format="turtle")
entities = [str(s) for s in g.subjects()]

if not entities:
    sparql.setQuery(query)
    sparql.setReturnFormat(TURTLE)
    graph_context_as_Turtle = sparql.queryAndConvert()
    print(graph_context_as_Turtle)

llm = ChatOpenAI(model='gpt-4-1106-preview', temperature=0)

rdfTemplate = PromptTemplate(
    input_variables = ["user_input_placeholder", "graph_context_as_Turtle"],
    template = "{user_input_placeholder} by extracting information from the RDF data in {graph_context_as_Turtle}"
)

rdfChain = LLMChain(llm = llm, prompt = rdfTemplate, verbose = True)
rdfResponse = rdfChain.run(user_input_placeholder = user_input_placeholder, graph_context_as_Turtle = graph_context_as_Turtle)

print(rdfResponse)
writeFile.write(rdfResponse)

readFile.close()
writeFile.close()
import requests

readFile = open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\upload_and_query_prompt.txt", "r")
lines = readFile.readlines()
# Set the repository ID and graph URI
repositoryID = lines[0].strip()
graphURI = lines[2].strip()
readFile.close()


# Define the API endpoint
url = f"http://localhost:7200/repositories/{repositoryID}/rdf-graphs/service?graph={graphURI}"

# Set the path to the Turtle file
turtleFilePath = 'D:/Andrei/ModellingTools/Graph_Modelling_Tool/Scripts/content_graph.ttl'

# Open the Turtle file and read its content
with open(turtleFilePath, 'r') as file:
    turtleContent = file.read()

# Set the headers for the request
headers = {
    'Content-Type': 'application/x-turtle'
}

# Make the POST request to load the Turtle file
response = requests.post(
    url.format(repositoryID=repositoryID, graphURI=graphURI),
    headers=headers,
    data=turtleContent
)

# Check the response status code
print(response.status_code)
if response.status_code == 200:
    print('Turtle file loaded successfully.')
else:
    print('Error loading Turtle file:', response.text)
readFile.close()

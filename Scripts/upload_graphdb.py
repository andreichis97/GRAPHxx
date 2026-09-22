import requests

with open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\repository_location.txt", "r") as readFile:
    url = readFile.readline().strip()
    blank_line = readFile.readline()  # Read and discard the blank line
    repository_id = readFile.readline().strip()
    print(f"URL: {url}")
    print(f"Repository ID: {repository_id}")

with open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\generated_file_type.txt", "r") as readFile:
    diagram_type = readFile.readline().strip()
    serialization_format = readFile.readline().strip()
    print(f"Diagram Type: {diagram_type}")
    print(f"Serialization Format: {serialization_format}")

# Define the API endpoint
if(url == ""):
    url = f"http://localhost:7200/repositories/{repository_id}/statements"
else:
    url = f"{url}/repositories/{repository_id}/statements"

# Set the path to the Turtle file
if serialization_format == "trig":
    headers = {
        'Content-Type': 'application/x-trig'
    }
    if diagram_type == "content":
        readFilePath = 'D:/Andrei/ModellingTools/Graph_Modelling_Tool/Scripts/content_graph.trig'
    else:
        readFilePath = 'D:/Andrei/ModellingTools/Graph_Modelling_Tool/Scripts/schema_graph.trig'
else:
    headers = {
        'Content-Type': 'application/x-turtle'
    }
    if diagram_type == "content":
        readFilePath = 'D:/Andrei/ModellingTools/Graph_Modelling_Tool/Scripts/content_graph.ttl'
    else:
        readFilePath = 'D:/Andrei/ModellingTools/Graph_Modelling_Tool/Scripts/schema_graph.ttl'

# Open the Turtle file and read its content
with open(readFilePath, 'r') as file:
    content = file.read()

# Make the POST request to load the Turtle file
response = requests.post(
    url.format(repository_id=repository_id),
    headers=headers,
    data=content
)

# Check the response status code
print(response.status_code)
if response.status_code == 200 or response.status_code == 204:
    print('File uploaded successfully.')
else:
    print('Error uploading file:', response.text)
#readFile.close()

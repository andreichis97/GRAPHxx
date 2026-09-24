from paths import SCRIPTS_DIR

import requests

with open(SCRIPTS_DIR / "repository_location.txt", "r") as readFile:
    url = readFile.readline().strip()
    repository_id = readFile.readline().strip()
    print(f"URL: {url}")
    print(f"Repository ID: {repository_id}")

with open(SCRIPTS_DIR / "generated_file_type.txt", "r") as readFile:
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
        readFilePath = SCRIPTS_DIR / "content_graph.trig"
    else:
        readFilePath = SCRIPTS_DIR / "schema_graph.trig"
else:
    headers = {
        'Content-Type': 'application/x-turtle'
    }
    if diagram_type == "content":
        readFilePath = SCRIPTS_DIR / "content_graph.ttl"
    else:
        readFilePath = SCRIPTS_DIR / "schema_graph.ttl"

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
with open(SCRIPTS_DIR / "upload_status.txt", "w") as statusFile:
    statusFile.write(f"Response Status Code: {response.status_code}\n")
    statusFile.write(f"Response Text: {response.text}\n")
    #if response.status_code == 200 or response.status_code == 204:
    #    statusFile.write('File uploaded successfully.\n')
    #else:
    #    statusFile.write('Error uploading file.\n')
#readFile.close()

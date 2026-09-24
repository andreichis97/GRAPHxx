from paths import SCRIPTS_DIR

from rdflib import Graph, plugin
from rdflib.serializer import Serializer

outfile = open(SCRIPTS_DIR / "jsonld_graph.json", "w")
infile = open(SCRIPTS_DIR / "content_graph.ttl", "r") #check for all possibilities

with open(SCRIPTS_DIR / "generated_file_type.txt", "r") as readFile:
    diagram_type = readFile.readline().strip()
    serialization_format = readFile.readline().strip()
    #print(f"Diagram Type: {diagram_type}")
    #print(f"Serialization Format: {serialization_format}")

if serialization_format == "trig":
    if diagram_type == "content":
        infile = open(SCRIPTS_DIR / "content_graph.trig", "r")
    else:
        infile = open(SCRIPTS_DIR / "schema_graph.trig", "r")
else:
    if diagram_type == "content":
        infile = open(SCRIPTS_DIR / "content_graph.ttl", "r")
    else:
        infile = open(SCRIPTS_DIR / "schema_graph.ttl", "r")

rdfContent = infile.read()

toSerialize = Graph().parse(data=rdfContent, format=serialization_format)

#print(toSerialize.serialize(format='json-ld', indent=4))

serialized = toSerialize.serialize(format='json-ld', indent=4)

outfile.write(serialized)

outfile.close()
infile.close()
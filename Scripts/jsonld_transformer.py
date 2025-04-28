from rdflib import Graph, plugin
from rdflib.serializer import Serializer

outfile = open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\jsonld_graph.json", "w")
infile = open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\content_graph.ttl", "r")

rdfContent = infile.read()

toSerialize = Graph().parse(data=rdfContent, format='turtle')

#print(toSerialize.serialize(format='json-ld', indent=4))

serialized = toSerialize.serialize(format='json-ld', indent=4)

outfile.write(serialized)

outfile.close()
infile.close()
lines_seen = set()
outfile = open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\content_graph.trig", "w")
infile = open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\raw_content_graph.trig", "r")
for line in infile:
    print(lines_seen)
    print(line)
    if line not in lines_seen:
        outfile.write(line)
        lines_seen.add(line)
infile.close()
outfile.close()
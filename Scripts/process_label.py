import random

readFile = open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\label_value.txt", "r")
writeFile = open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\processed_local_identifier.txt", "w")
rawLabel = readFile.read()

spaceCounter = 0
spacePositions = []
letterCounter = 0
processedUri = ""
firstPartUri = ""
secondPartUri = ""
#print(rawLabel)
#writeFile.write(rawLabel)

labelLetters = list(rawLabel.strip(" "))
print(labelLetters)

for i in labelLetters:
    letterCounter = letterCounter + 1
    if i == " ":
        spaceCounter = spaceCounter + 1
        spacePositions.append(letterCounter)
        if(spaceCounter == 1):
            slicer = slice(letterCounter-1)
            firstPartUri = labelLetters[slicer]
    if(spaceCounter == 0):
        slicer = slice(letterCounter)
        firstPartUri = labelLetters[slicer]

#print(firstPartUri)
#print(spacePositions)
processedUri = ''.join(firstPartUri)
#print(processedUri)

for i in spacePositions:
    secondPartUri = secondPartUri + labelLetters[i]
#print(secondPartUri)

randomIdentifier = (random.randint(0, 999999))
processedUri = processedUri + secondPartUri + "_" + str(randomIdentifier)
print(processedUri)

writeFile.write(processedUri)


readFile.close()
writeFile.close()
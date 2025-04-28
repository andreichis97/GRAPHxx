import random

readFile = open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\label_value.txt", "r")
writeFile = open("D:\\Andrei\\ModellingTools\\Graph_Modelling_Tool\\Scripts\\processed_local_identifier.txt", "w")
rawLabel = readFile.read()

wordCounter = 0
processedUri = ""
firstPartUri = ""
secondPartUri = ""
#print(rawLabel)
#writeFile.write(rawLabel)

labelWords = rawLabel.split()
#print(labelLetters)

#print(labelWords[0])

for i in labelWords:
    wordCounter = wordCounter + 1
    if wordCounter == 1:
        val = str(labelWords[wordCounter-1])
        val = val.lower()
        processedUri = processedUri + val
    else:
        val = str(labelWords[wordCounter-1])
        val = val.capitalize()
        processedUri = processedUri + val


#randomIdentifier = (random.randint(0, 999999))
#processedUri = processedUri + "_" + str(randomIdentifier)
#print(processedUri)

writeFile.write(processedUri)


readFile.close()
writeFile.close()
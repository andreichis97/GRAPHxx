# GRAPHxx
This repository contains the scripts and the ABL file for the GRAPHxx Modeling Tool

In order to use GRAPHxx you will firstly need to download ADOxx https://www.adoxx.org/live/download-guided
ADOxx comes with 2 parts: ADOxx Development Toolkit and ADOxx Modeling Toolkit
The GRAPHxx.abl file needs to be imported in the ADOxx Development Toolkit as a new library and then a user must be created and assigned to it
The Scripts folder contains all the files that implement the functionalities of the modeling tool such as generating Turtle code from diagrams. After the folder is downloaded, in the ADOxx Development Toolkit the following actions need to be done:
1) Select the "Library Management" tab
2) Click on "Settings"
3) Expand the GRAPHxx 2.0 library and click on "GRAPHxx 2.0 Dynamic"
4) Click on "Library attributes" from the side menu
5) Click on the "Add-ons" tab
6) In the "External Coupling" part click on "Large text field" (icon looking like a square)
7) You'll see some file paths that need to be modified in order to point to the location of the Scripts folder

The Evaluation_Scripts folder contains some AdoScript that generates graph instances automatically
All the Python scrips where developed on Python 3.10.4


# GRAPHxx Modeling Tool

GRAPHxx is an ADOxx-based modeling tool for creating and managing knowledge graphs through diagrammatic models. This repository contains the GRAPHxx library (GRAPHxx.abl) and the AdoScript and Python scripts implementing its functionality, including RDF serialization, RDF import, SPARQL requests, and GraphRAG workflows.

The implementation available in this repository is fully compatible with Windows machines. For MacOS, there are several functionalities that need adjustments so please reach out via GitHub for help.

Repository contents

GRAPHxx_v11.abl — the modeling library to import into ADOxx.

Scripts/ — the .asc and .py files implementing the tool's functionality, together with their supporting files.
requirements.txt — containing the Python dependencies to install before using the Python-based functionality is included in Scripts/

Evaluation_Scripts/ — AdoScript scripts for automatically generating graph instances for evaluation.


Prerequisites

- ADOxx, including the Development Toolkit and Modeling Toolkit. Download ADOxx and obtain a license key from the official ADOxx website. ADOxx can be downloaded from the following link: https://www.adoxx.org/

- Python. The scripts were developed and tested on Python 3.12.8.

- GraphDB, if you want to use direct SPARQL requests or GraphRAG integration. The integration was tested with GraphDB 10.7.4.

- For workflows that call an external AI service, a valid OpenAI API key and access to the models used by the scripts.


Installation and configuration

1. Download the repository

Clone the repository or download and extract it. Keep the scripts and their supporting files together, preserving the repository's folder structure. Choose a location where your user account can read and write files.

2. Import the GRAPHxx library

Open the ADOxx Development Toolkit.

Import GRAPHxx.abl as a new library.

Create an ADOxx user and assign that user to the imported GRAPHxx library.

Use this user when opening GRAPHxx in the ADOxx Modeling Toolkit.

3. Set the scripts working directory

In the GRAPHxx library initialization code, update the global AdoScript variable graphxxScriptsDir to the absolute path of the folder containing the .asc and .py scripts.
To do this, open the Library management tab from ADOxx Development Toolkit -> Click Settings -> Click on the + button near GRAPHxx 2.0 to expand the library -> Click GRAPHxx 2.0 Dynamic -> Click library attributes -> Click Add-ons -> In External coupling modify the SETG graphxxScriptsDir: ... line and set the path to the Scripts/ folder from your machine.

For example:

SETG graphxxScriptsDir:"D:\\GRAPHxx\\Scripts"

Replace the example path with the actual path on your machine. Point to the scripts folder itself, not the repository root or an individual script. Preserve the doubled backslashes shown in the AdoScript string.


Save the library changes and restart the Modeling Toolkit so the initialization code runs with the updated value. If you later move the scripts folder, update this variable again.

4. Create a Python virtual environment and install dependencies

Create the virtual environment inside the folder containing the .asc and .py scripts. The following example names it .venv; this name must match the environment folder referenced by the AdoScript Python-launch commands.

Virtual environments can be created using the command prompt or directly from an IDE la Visual Studio Code.

Run .venv\Scripts\python.exe -m pip install -r requirements.txt or pip install -r requirements.txt from the IDE opened in the Scripts/ folder, after the virtual environment (.venv) was created.
 

ADOxx must launch Python using this virtual environment's interpreter, for example D:\GRAPHxx\Scripts\.venv\Scripts\python.exe. Installing dependencies in the environment does not make them available to a different Python interpreter.

These commands invoke the environment's interpreter directly, so activation is unnecessary. If you move the project to another location or machine, recreate the virtual environment there and reinstall the dependencies.

5. Configure GraphDB and AI access

Direct integration is currently available only with GraphDB for sending SPARQL requests and running GraphRAG workflows. This integration was tested with GraphDB 10.7.4.


Before using these features:

Start GraphDB and create or select a repository.

Load the RDF data you want to query into that repository.

Supply the GraphDB connection details and repository identifier requested by the relevant GRAPHxx workflow.

For AI-powered workflows, configure the API key and model settings required by the corresponding scripts. The OpenAI API key has to be added in the api_keys_example.py file. After the key is added, rename the file to api_keys.

GraphDB is needed for the integrated repository workflows, rather than for editing diagrams or exporting local RDF files.

Verify the setup

Open the ADOxx Modeling Toolkit with the user assigned to GRAPHxx. Create a small model and try exporting it to Turtle. If using the GraphDB integration, first send a simple SPARQL query to a populated repository, then try a GraphRAG question.

If a Python-based operation fails, check the graphxxScriptsDir value, the interpreter path used by AdoScript, and whether the dependencies were installed in that interpreter's virtual environment. For repository or AI errors, also check the connection settings, API credentials, and model access.

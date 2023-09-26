# Required Libraries
import spacy
import PyPDF2
import pathlib
import pandas as pd
from spacy import displacy
from spacy.tokens import DocBin
import json
from datetime import datetime
from tqdm import tqdm
import re 

# Useful context and references:
# https://spacy.io/
# https://spacy.io/usage/training#config
# https://levelup.gitconnected.com/auto-detect-anything-with-custom-named-entity-recognition-ner-c89d6562e8e9
 
# Initial Setup
# pdf(s) to feed the trained the model - will need to change based on desired paper
pdfpath = '10.3099_0027-4100-163.1.1.pdf'

# this dictionary will contain all annotated examples with structure_training_data
collective_dict = {'TRAINING_DATA': []}

# Converts a research paper in pdf format to txt format 
def pdf_to_text(pdfpath):
    
    # opens pdf version of research paper
    pdffileobj=open(pdfpath,'rb')
    
    # reads the pdf 
    pdfreader=PyPDF2.PdfReader(pdffileobj)
 
    # printing number of pages in pdf file
    print(len(pdfreader.pages))

    # get number of pages and set as an iterible variable
    num_pages = len(pdfreader.pages)

    with open('paper.txt','w', encoding='utf-8') as f:
    # extracting text from each page
        for i in range(0, num_pages):
            page = pdfreader.pages[i]
            text = page.extract_text()
            f.write(text)
    f.close

    # load the spacy nlp ner model
    nlp = spacy.load('en_core_web_sm')

    # load paper with text extracted
    file_name = 'paper.txt'
    # load training text
    doc = nlp((pathlib.Path(file_name).read_text(encoding="utf-8")))

    # load results to file
    with open('results.txt','w', encoding='utf-8') as g:
        for ent in doc.ents:
            g.write(ent.text+' -- '+ent.label_+' -- '+spacy.explain(ent.label_))
    g.close

# Creates a Training Data Set and puts it in the required format
def structure_training_data(text, kw_list):
    results = []
    entities = []
    
    # search for instances of keywords within the text (ignoring letter case)
    for kw in tqdm(kw_list):
        search = re.finditer(kw, text, flags=re.IGNORECASE)
        
        # store the start/end character positions
        all_instances = [[m.start(),m.end()] for m in search] 
        
        # if the callable_iterator found matches, create an 'entities' list
        if len(all_instances)>0:
            for i in all_instances:
                start = i[0]
                end = i[1]
                entities.append((start, end, "SPECIMEN"))
            
        # alert when no matches are found given the user inputs
        else:
            print("No pattern matches found. Keyword:", kw)
                
    # add any found entities into a JSON format within collective_dict
    if len(entities)>0:
        results = [text, {"entities": entities}]
        collective_dict['TRAINING_DATA'].append(results)
        return

# Takes the Training Data Set and puts it the .spacy format required by Spacy 
def create_training_data(TRAIN_DATA):
    db = DocBin()
    
    # create a blank model
    nlp = spacy.blank('en')

    for text, annot in tqdm(TRAIN_DATA):
        doc = nlp.make_doc(text)
        ents = []

        # create span objects
        for start, end, label in annot["entities"]:
            span = doc.char_span(start, end, label=label, alignment_mode="contract") 

            # skip if the character indices do not map to a valid span
            if span is None:
                print("Skipping entity.")
            else:
                ents.append(span)
                # handle erroneous entity annotations by removing them
                try:
                    doc.ents = ents
                except:
                    # print("BAD SPAN:", span, "\n")
                    ents.pop()
        doc.ents = ents

        # pack Doc objects into DocBin
        db.add(doc)

    return db   

# Currently not used as the model can be trained via Spacy CLI
def train_spacy_ner_model(text):

    # load the spacy nlp ner model
    nlp = spacy.load('en_core_web_sm')

    # load training text
    doc = nlp(text)

    # load results to file
    with open('results.txt','w') as g:
        for ent in doc.ents:
            g.write(ent.text+' -- '+ent.label_+' -- '+spacy.explain(ent.label_))
    g.close

# Feeds research paper in .txt format into the trained model
def feed_trained_model(text_to_feed,trained_model):
    
    trained_model = trained_model

    # load the trained model
    nlp_output = spacy.load(trained_model)

    # load paper with text extracted
    file_name = text_to_feed #'paper.txt'

    # pass our paper.txt into the trained pipeline
    doc = nlp_output((pathlib.Path(file_name).read_text(encoding="utf-8")))

    # customize the label colors
    colors = {"SPECIMEN": "linear-gradient(90deg, #E1D436, #F59710)"}
    options = {"ents": ["SPECIMEN"], "colors": colors}

    # visualize the identified entities
    displacy.render(doc, style="ent", options=options)

    # print out the identified entities
    for ent in doc.ents:
        if ent.label_ == "SPECIMEN":
            print(ent.text, ent.label_)

# Example Usage of pdf_to_text to convert a pdf research paper into .txt format
pdf_to_text(pdfpath)

# Example creation of a training data set using structure_training_data and create_training_data
text1 = "The samples studied by Kathriner et al. (2014) as H. tenkatei are nested within this clade \
        (CAS206638, ZRC26167, CAS208159, and CAS 229632). H. tenkatei was elevated to a valid species based \
        on the examination of the type specimens by Rösler and Glaw (2010)."

structure_training_data(text1, ['CAS206638', 'CAS208159', 'CAS 229632'])

TRAIN_DATA = collective_dict['TRAINING_DATA']

TRAIN_DATA_DOC = create_training_data(TRAIN_DATA)

TRAIN_DATA_DOC.to_disk("TRAIN_DATA.spacy")

# Example of training the model using Spacy CLI and a base_config.cfg file (from Spacy documentation: https://spacy.io/usage/training#config)
# python -m spacy init fill-config base_config.cfg.txt config.cfg 
# python -m spacy train config.cfg --output ./output 

# Example of passing a paper.txt document into the trained model
feed_trained_model('paper.txt',"output/model-best")
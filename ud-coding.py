#!/usr/local/bin/python3

__author__ = "Achim Stein"
__version__ = "1.7 for CMLF 2024"
__email__ = "achim.stein@ling.uni-stuttgart.de"
__status__ = "18.4.24"
__license__ = "GPL"

import sys, os, json, io
from io import StringIO
import argparse, re
import csv
import pandas as pd
import datetime
from collections import defaultdict   # init dicts with value type
from grewpy import Graph, CorpusDraft, Request, Corpus, request_counter
from grewpy import Corpus, GRSDraft, Rule, Commands, GRS, set_config
from nltk.grammar import DependencyGrammar
from nltk.parse import DependencyGraph, ProjectiveDependencyParser, NonprojectiveDependencyParser
from conllu import parse, parse_incr, parse_tree


# global vars
codingAtt = []  # collect coding attributes in this list
wholeCorpus = {} # a grewpy CorpusDraft object

# global vars for HTML corpus on server
# global variables
htmlServer = "http://141.58.164.21"  # julienas (IP Nr reduces table file size)
lastFile = ''  # HTML text file
htmlHead = '''<!DOCTYPE html>
<html>
  <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
  <head>
    <title>FTPUB: %s</title>
    <style>
      .parse p {
        font-family: monospace;/* Web-safe typewriter-like font */
        overflow: hidden;/* Ensures the content is not revealed until the animation */
        border-left: .17em solid blue;/* The typewriter cursor */
        white-space: nowrap;/* Keeps the content on a single line */
        margin: 0 auto;/* Gives that scrolling effect as the typing happens */
        letter-spacing: 0em;/* Adjust as needed */
      }
      .coding {
        background:gray; color:yellow; font-family: "Courier New", Courier, monospace; font-size: 10px;
      }
      .a { color:white; font-weight: bold; } /* attribute in coding*/
      .v { background-color:yellow; }        /* verb in coding*/
      .l { color:magenta; }        /* lemma */
      .u { color:DarkGreen; }        /* upos */
      .x { color:Olive; }        /* xpos */
      .d { color:blue; }        /* dependency relation */
    </style>
  </head>
  <body>
'''
htmlFoot='''  </body>
</html>
'''
htmlSource = '''
<hr>
<font color="red">
<a href="https://www.atilf.fr/ressources/frantext/">Frantext Public Domain Texts</a>.<br>
These texts are labelled as 'public domain' in the <i>Frantext</i> database.
License restrictions may apply when re-using the data.<br>
Coding and HTML conversion by ILR (University of Stuttgart)<br>
French lemmatization using RNN (Schmid 2019; LMU München) and BFM training data (A. Lavrentev, IHRIM, ENS de Lyon)<br>
%s %s (%s)<br>
<a href="index.html">List of files</a>
</font>
''' % (os.path.basename(__file__), __version__, str(datetime.date.today()))
corpusName = 'FTPUB1'  # default
htmlDir = "ft"


# -------------------------------------------------------
# functions
# -------------------------------------------------------
def readRequests():
    # parse the TSV file containing GREW requests
    print(f"Reading grew requests from file {args.request}")
    requests = open(args.request, 'r')
    patterns = {}  # store requests in this dictionary
    without = {}  # store negative requests in this dictionary
    requestDict = {}  # store requests with key att=val in this dictionary
    for row in csv.reader(requests, delimiter ='\t', quoting=csv.QUOTE_NONE):
        if re.search(r'#.*STOP', ''.join(row)):
            break
        if re.search(r'#', ''.join(row)):
            continue
        if any(row):   # avoid errors with empty lines
            if len(row) <= 3:
                if re.search(r'=', row[0]):
                    att = row[0].split('=')[0]
                    val = row[0].split('=')[1]
                    if len(row) == 3:
                        without[row[0]] = row[2]
                else:
                    print(f"  Ignoring line: format should be att=val, but is: {row[0]}")
                patterns[row[0]] = row[1]
            else:
                print(f"  Ignoring line: wrong number of columns: {row} ({len(row)})")
    print(f"  {len(patterns.keys())} request(s) to be processed.")
    # store request objects in a dictionary, with att=val as key
    for key in patterns.keys():
        objRequest = Request()  # initialize the request pattern
        objRequest.append('pattern', patterns[key])
        if key in without.keys():
            objRequest.append('without', without[key])
        requestDict[key] = objRequest
    print()
    return(patterns, without, requestDict)

def processRules (udCorpus, requestDict):
    # udCorpus is a grew Corpus object
    # wholeCorpus is a grew CorpusDraft object (i.e. a dictionary that can be modified)
    # --------------------------
    # for each request rule, apply it to the Corpus (udCorpus)
    #   - each rule returns a list of matching graphs
    #     e.g.: '10040': [{'V': '6', 'C': '3'}, {'V': '10', 'C': '7'}],
    #   - for each att-value pair, the match list is stored in a dictionary
    foundRuleList = defaultdict(list)
    matchedRules = defaultdict(list)
    print(f"Matching {len(udCorpus)} graphs against rules...", end = '\n')
    for attVal in requestDict.keys():
        foundList = udCorpus.search(requestDict[attVal])  # list of JSON matches, with sent_id, nodes, edges
        matchedRules[attVal] = len(foundList)
        if len(foundList) > 0:
            foundRuleList[attVal] = foundList

    # for each att-value pair get the list
    ruleCount = 0
    for attVal in foundRuleList.keys():   ## patterns.keys():
        ruleCount += 1
        print(f"  Adding coding for rule {ruleCount} of {len(foundRuleList.keys())}:  {attVal} ({matchedRules[attVal]} matches)") #  <- {requestDict[attVal]} 
        listMatches = foundRuleList[attVal] # this is the list of matching graphs (json)
        # for each match in the list, add the coding to the listed sentences
        #   e.g. [{'sent_id': '3', 'matching': {'nodes': {'V': '3', 'C': '5'}, 'edges': {}}}]
        node2 = 0  # dummy node, will be filled in addCoding()
        for thisList in listMatches:
            thisID = thisList['sent_id']
            thisDict = thisList['matching']['nodes']
            if 'C' in thisList['matching']['nodes'].keys():
                node2 = thisDict['C']
            graph = wholeCorpus[thisID]
            wholeCorpus[thisID] = addCoding(graph, thisDict['V'], attVal, node2)  # update meta info of this graph

    udCorpus.clean() # free memory
    return(wholeCorpus) # return the modified CorpusDraft object

def addCoding (js, govNode, codingString, node2):
    # for graph js, add a coding attribute to meta and append codingString
    global codingAtt
    codingIndex = "coding_" + govNode
    # initialize new coding string with verb info (if available)
    if not codingIndex in js.json_data()["meta"]:
        js.json_data()["meta"][codingIndex] = ''
        for att in ["textform", "lemma", "xpos"]:
            if att in js.json_data()['nodes'][govNode].keys():
                js.json_data()["meta"][codingIndex] += ';' +att+'='+js.json_data()['nodes'][govNode][att] 
                if not att in codingAtt:
                    codingAtt.append(att)  # collect attributes in a list
        js.json_data()["meta"][codingIndex] = js.json_data()["meta"][codingIndex][1:]
    # ...append coding string to existing string
    thisAtt, thisVal = codingString.split('=')
    thisAtt = re.sub(r';', '_', thisAtt)
    # Option --first_rule: don't overwrite this attribute
    if args.first_rule and re.search(';'+thisAtt+'=', js.json_data()["meta"][codingIndex]):
        return(js)
    else:
        js.json_data()["meta"][codingIndex] += ';' + codingString
        # add attribute to list
        if not thisAtt in codingAtt:
            codingAtt.append(thisAtt)  # append to the global list of attributes
        # add info for second node (TODO: experimental)
        if args.keep_target_node_info:
            if node2 != 0:
                node2Info = str(node2)
                if 'textform' in js.json_data()['nodes'][node2].keys():
                    node2Info += '_' + js.json_data()['nodes'][node2]['textform']
                js.json_data()["meta"][codingIndex] += '(' + node2Info + ')'
    return(js)

def checkIDs (udCorpus):
    # for each Graph in udCorpus, add meta information sent_id and text if not existant
    print(f"Verifying or inserting meta information...")
    sNr = 0
    found = corrected = nameAdded = 0
    output = []
    for s in udCorpus:
        sNr += 1
        graph = udCorpus[s]
        if 'sent_id' in graph.json_data()["meta"]:
            found += 1
        else:
            graph.json_data()["meta"]['sent_id'] = str(sNr)
            corrected +=1
        if not 'text' in graph.json_data()["meta"] and '' in graph.json_data()["meta"]:
            graph.json_data()["meta"]['text'] = graph.json_data()["meta"]['']
            del graph.json_data()["meta"]['']
            nameAdded +=1
        output.append(graph)
    correctedCorpus = Corpus(output)
    print(f"   Finished sent_id check: found={found}, inserted={corrected}, nameAdded={nameAdded}")
    return(correctedCorpus, corrected)

def writeTable(output):
    # converts the output (list of graph objects) to a table
    global codingAtt
    codingAtt.insert(0, 'node')
    codingAtt.insert(0, 'sent_id')
    codingAtt.insert(0, 'date')
    codingAtt.insert(0, 'text')
    codingAtt.insert(0, 'url')
    codingAtt.insert(0, 'text_id')
    reCoding = re.compile('coding_(\d+)')  # label for coding strings
    graphCodingDict = defaultdict() # codings for all the graphs
    nrCodingDict = defaultdict()    #   for each coding line of one graph
    attValDict = defaultdict()      #   for att-value pairs in one coding line
    countLine = 0
    out = open(args.table, 'w', newline='')
    writer = csv.DictWriter(out, fieldnames=codingAtt, delimiter='\t') # attValDict.keys()  , quoting=csv.QUOTE_MINIMAL
    writer.writeheader()
    print(f"Writing the coding table to {args.table}...", end='')
    for graph in output:
        outRows = {}  
        countLine += 1
        if 'sent_id' in graph.json_data()["meta"].keys():
            thisID = graph.json_data()["meta"]['sent_id']
        else:
            thisID = 'graph_' + str(countLine)

        # for each meta line
        for meta in graph.json_data()["meta"]:
            attValDict = {} # init dict for att-val pairs
            for att in codingAtt:
                attValDict[att] = '_'  # default value
            if 'text_id' in graph.json_data()["meta"].keys():
                attValDict["text_id"] = graph.json_data()["meta"]['text_id']
            if args.html:  # add a column for URLs pointing to corpus on server
                if args.html_file:  # specific html file
                    url = '=HYPERLINK(\"{}/{}/{}#{}\"; \"WWW\")'.format(htmlServer, htmlDir, args.html_file, graph.json_data()["meta"]['sent_id'])
                else:          # default: name of html file is text_id
                    url = '=HYPERLINK(\"{}/{}/{}#{}\"; \"WWW\")'.format(htmlServer, htmlDir, graph.json_data()["meta"]['text_id'], graph.json_data()["meta"]['sent_id'])
                attValDict["url"]  = url
            if 'text' in graph.json_data()["meta"].keys():
                attValDict["text"] = graph.json_data()["meta"]['text']
            if 'date' in graph.json_data()["meta"].keys():
                attValDict["date"] = graph.json_data()["meta"]['date']
            attValDict["sent_id"] = thisID
            if re.search(reCoding, meta):
                codeNr = re.search(reCoding, meta).group(1)
                codeStr = graph.json_data()['meta'][meta]
                # split att-value pairs and store in att-value dictionary
                pairs = codeStr.split(';')
                attValDict["node"] = codeNr
                for pair in pairs:
                    if pair.count('=') == 1:
                        attribute, value = pair.split('=')
                    else:
                        attribute = pair[:pair.find('=')]
                        value = pair[pair.find('='):] + "_ERROR"
                        print(f"  WARNING: pair {pair} is not well formed")
                    if attribute in codingAtt:   # only if in pre-defined columns
                        if args.keep_target_node_info:
                            value = re.sub(r'\(.*', '', value)
                        attValDict[attribute] = value
                    else:               
                        print(f"  WARNING: skipping undefined attribute in pair: '{pair}'")
                outRows[codeNr] = attValDict  # temporarily store in dict
        # print row for numerically sorted nodes
        sorted_keys = sorted(outRows.keys(), key=lambda x: int(x))
        for key in outRows:
            values = [str(value) for value in outRows[key].values()]
            row = '\t'.join(values) + '\n'
            out.write(row)
    print("Done.")
    return()

def compareTable(df1, df2):
    # compare this table to the input file table
    # df1 = conll coding
    # df2 = mcvf coding  (argument of -c)
    print(f"Comparing tables...")
    columns_to_compare = ['join', 'clause', 'subj', 'dobj', 'iobj'] # , 'pobj', 'refl'
    # make df1 compatible: rename and replace
    df1 = df1.rename(columns={'text':'textid', 'pobj_agent':'pobj'})
    df1['textid'] = df1['textid'].replace({'#':'', 'TEST':'TEST'}, regex=True)
    df1['subj'] = df1['subj'].replace({'pred':''}, regex=True)  # copulas: e.g. predpro > pro
    df1['subj'] = df1['subj'].replace({'pass':''}, regex=True)  # passive: e.g. passpro > pro
    df1 = df1.replace({'_':'0'}, regex=True)
    df1 = df1.replace({'=':''}, regex=True)
    df1 = df1.fillna('0')  # because 'null' is imported as 'NaN'
    # make df2 compatible
    df2 = df2.rename(columns={'reflself':'refl','ipType':'clause'})
    df2['textid'] = df2['textid'].replace({'_\d+$':''}, regex=True)
    df2 = df2.drop(columns=['URLwww', 'URLlok', ], errors='ignore')
    df2['subj'] = df2['subj'].replace({'proimp':'pro'}, regex=True)
    df2['subj'] = df2['subj'].replace({'nullcon|nullpro':'0'}, regex=True)
    df2['dobj'] = df2['dobj'].replace({'prd':'pred'}, regex=True)
    df2['dobj'] = df2['dobj'].replace({'clit.*':'pro'}, regex=True)
    df2['dobj'] = df2['dobj'].replace({'lex-trace':'pro'}, regex=True)
    df2['dobj'] = df2['dobj'].replace({'quant':'lex'}, regex=True)
    # make a join key with textid and verbform (this won't work if a verb occurs twice)
    df1['join'] = df1['textid'] + '_' + df1['textform']
    df2['join'] = df2['textid'] + '_' + df2['form']
    print(df1.head())
    print(df2.head())
    # Merge DataFrames on 'textid' to compare specified columns
    merged_df = pd.merge(df1[columns_to_compare], df2[columns_to_compare], on='join', suffixes=('_1', '_2'))
    # Iterate through the columns and update the match scores
    merged_df['cmp_sum'] = 0
    scoreColumns = columns_to_compare
    scoreColumns.remove('join')
    for column in scoreColumns:
        merged_df['cmp_sum'] += (merged_df[f'{column}_1'] == merged_df[f'{column}_2']).astype(int)
    for column in ['subj', 'dobj', 'iobj']:
        merged_df[f'cmp_{column}'] = merged_df[f'{column}_1'].eq(merged_df[f'{column}_2']).astype(int)
    # Add a bottom line for scores
    total_rows = len(merged_df)
    evalColumns = ['cmp_subj', 'cmp_dobj', 'cmp_iobj']
    # Create a new DataFrame with the column sums
    columnSums = (merged_df[evalColumns].sum()/total_rows).round(2)  # .sum() creates a pandas series
    sumRow = pd.DataFrame([columnSums.values], columns=evalColumns, index=['Sum'])
    # Display the DataFrame with match scores
    print(f"\n--------> Results subj:\n{sumRow}")
    new_df = pd.concat([sumRow, merged_df])
    errorStats(merged_df, "subj_1", "subj_2")
    print(f"\n--------> Results dobj:\n{sumRow}")
    new_df = pd.concat([sumRow, merged_df])
    errorStats(merged_df, "dobj_1", "dobj_2")
    return(new_df)

def errorStats (df, col1, col2):
    mismatch_dict = {}
    # Iterate through rows and compare values in the specified columns
    for index, row in df.iterrows():
        value1 = row[col1]
        value2 = row[col2]
        if value1 != value2:
            mismatch_pair = (value1, value2)  # a tuple, used as key in our dict
            mismatch_dict[mismatch_pair] = mismatch_dict.get(mismatch_pair, 0) + 1
    # sort and print the frequencies of mismatching pairs
    sorted_mismatches = dict(sorted(mismatch_dict.items(), key=lambda x: x[1], reverse=True))
    print(f">>>> {col1}-{col2} mismatches:")
    for pair, frequency in sorted_mismatches.items():
        print(f"\t{frequency}\t{pair}")

# -------------------------------------------------------
# main
# -------------------------------------------------------
def main (args):
    global wholeCorpus

    # compare two coding tables, then exit
    if args.compare_table != '':   # -c
        with open(args.file_name, 'r') as input:
            table1 = pd.read_csv(input, delimiter='\t')
            input.close()
        with open(args.compare_table, 'r') as input:
            table2 = pd.read_csv(input, delimiter='\t')
            input.close()
        merged = compareTable(table1, table2)
        print(f"Writing merged table to file {args.out_file}")
        merged.to_csv(args.out_file, sep='\t', index=False)
        exit(0)

    # regular call for CoNLL-U input
    try:
        with open(args.file_name, 'r') as input:
            data = input.read()
    except FileNotFoundError:
        print("file not found", args.file_name)
        quit()

    # read requests from tsv file
    if args.request != '':   # -r
        patterns, without, requestDict = readRequests()
    else:
        print(f"A file with grew requests is required (option -r)")
        exit(1)

    # option -C: verify or add sent_id to graph meta data
    originalCorpus = Corpus(data)
    if args.check_ids:
        print(f"Verifying sent_id in the corpus...")
        originalCorpus, corrected = checkIDs(originalCorpus)
        tmpFile = 'tmp_' + re.sub(r'.*/', '', args.file_name)
        print(f"Writing the corpus with corrected IDs to temp file: {tmpFile}")
        with open(tmpFile, 'w') as out:
            for graph in originalCorpus:
                out.write(originalCorpus[graph].to_conll() + '\n')
            out.close()
        print(f"  Re-importing the corpus from temp file: {tmpFile}")
        with open(tmpFile, 'r') as input:
            data = input.read()
            input.close()
    # re-read the data into a global CorpusDraft object (= a modifiable dictionary)
    print(f"Creating grewpy CorpusDraft...")
    wholeCorpus = CorpusDraft(data)
    # a Corpus object that can be searched using .search()
    print(f"Processing rules...")
    codedCorpus = processRules(Corpus(originalCorpus.to_conll()), requestDict)

    # output corpus as CoNLL-U        
    print(f"Writing the output to {args.out_file}...\n", end='')
    sorted_keys = sorted(codedCorpus.keys(), key=lambda x: int(x))
    codedCONLLU = []  # store coded conllu for HTML export
    with open(args.out_file, 'w') as out:
        for key in sorted_keys:
            conll = codedCorpus[key].to_conll()
            out.write(conll + '\n')
            codedCONLLU.append(conll)
    print(f"Codings written for {len(sorted_keys)} graphs.")

    # Function to redirect stdout to a string buffer
    def redirect_stdout_to_buffer():
        sys.stdout = StringIO()

    # Function to restore stdout
    def restore_stdout():
        sys.stdout = sys.__stdout__

    # convert the tree to HTML and add dependencies
    def tree_to_html(tree_str, xpos, deps):
        lines = tree_str.strip().split("\n") # Split the tree string into lines
        # sort lines based on word numbers (print_tree orders according to hierarchy, e.g. root in first line etc)
        lines = sorted(lines, key=lambda line: int(re.search(r'\[(\d+)\]', line).group(1)))
        # Convert each line to HTML node with proper indentation using dots
        html_nodes = []

        def repl(match):  # returns string for re.sub below
            wID = int(match.group(1))  # Evaluate the variable or expression
            return f"xpos:{xpos.get(wID, '')} [{wID}:{deps.get(wID, '')}]"  # return id:head, e.g.  [5:6]

        for line in lines:
            wID = re.search(r'\[(\d+)\]', line).group(1)
            wID = int(wID)
            line = re.sub(r'\[(\d+)\]', repl, line)
            leading_spaces = len(line) - len(line.lstrip(' ')) # Count the number of leading spaces
            indented_line = '.' * leading_spaces + line.lstrip() # Replace leading spaces with dots
            # Convert indented line to HTML node
            html_nodes.append("{}".format(indented_line))
        html_branch = "{}<br/>".format("".join(html_nodes)) # format HTML nodes
        html_tree = "{}".format(html_branch) # format the entire HTML branch

        """
        change tree format and insert html codes. Tree looks like this:
        (deprel:root) form:souhaite lemma:souhaiter upos:VERB [3:0]
            (deprel:cc) form:et lemma:et upos:CCONJ [1:3]
        """
        html_tree = re.sub(
            r'(\.+)?\(deprel:(.*?)\)(.*?)\[(\d+):(\d+)\]',
            lambda m: f"{int(m.group(4)):02d}{'' if m.group(1) is None else m.group(1)}{m.group(3)} <span class=d>{m.group(2)}</span>&#8594;{m.group(5)}<br/>\n",
            html_tree
        )
        html_tree = re.sub(r'lemma:(.*?) ', r'<span class=l>\1</span> ', html_tree)
        html_tree = re.sub(r'upos:(VER[A-Z]+) ', r'<span class=v>\1</span> ' , html_tree)
        html_tree = re.sub(r'upos:(.*?) ', r'<span class=u>\1</span> ', html_tree)
        html_tree = re.sub(r'xpos:(.*?) ', r'<span class=x>\1</span> ', html_tree)
        html_tree = re.sub(r'form:(.*?) ', r'<b>\1</b> ', html_tree)
        html_tree = re.sub(r'(\.\.+)', r'<span class=dot>\1</span> ', html_tree)

        return html_tree


    # create a HTML version of the output
    if args.html:
        # make dir for HTML files
        os.makedirs(htmlDir, exist_ok=True)
        if not os.path.isdir(htmlDir):
            print("Directory '%s' created\n" % htmlDir)

        textCode = htmlFile = re.sub(r'.*/', '', args.out_file)
        textCode = re.sub(r'.*/', '', textCode)  # strip path
        textCode = re.sub(r'\..*', '', textCode)  # strip suffix
        htmlFile = re.sub('conllu', 'html', htmlFile)
        print(f"Writing HTML output to {htmlFile}...")
        sentences = parse('\n'.join(codedCONLLU))
        trees = parse_tree('\n'.join(codedCONLLU))
        tree_strings = []     
        
        #  create index.html unless it exists
        if not os.path.isfile(htmlDir+'/index.html'):
            with open(htmlDir+'/index.html', 'w') as file:
                file.write(htmlHead + '\n\n')
                file.write(htmlSource + '\n\n<br/>')
        # add link to this file
        with open(htmlDir+'/index.html', 'a') as file:
            file.write('<br/>\n<a href="%s">%s</a>' % (htmlFile, htmlFile))  # add link to index file            
        """
        Using the conllu module, we loop through the sentences and the print_tree representations
        Since print_tree goes to stdout, we capture the output as string, then convert the string to HTML
        """
        with open(htmlDir + '/' + htmlFile, 'w') as out:
            anchorList = [] # store anchors for index.html
            out.write(htmlHead % textCode + '\n\n')
            for s in range(len(sentences)):   # loop through sentences in file (TokenList objects)
                # retrieve metadata entries
                metadata = sentences[s].metadata
                sCode = metadata['sent_id']
                bib = ''  # add metadata to the output
                if 'author' in metadata:
                    bib = "{}{}:".format(bib, metadata["author"])
                if 'title' in metadata:
                    bib = "{} <i>{}</i>".format(bib, metadata["title"])
                if 'date' in metadata:
                    bib = "{} ({})".format(bib, metadata["date"])
                if bib != '':
                    bib = "{}<br/>\n".format(bib)
                # add coding metadata: Iterate over metadata dict
                coding_lines = []
                for key, value in metadata.items():
                    if key.startswith('coding_'):
                        nr = re.sub(r'coding_', '', key)
                        value = re.sub(r'(lemma|upos|xpos)=.*?;', r'', value)
                        value = re.sub(r'textform=(.*?);', r'<b>\1</b>: ', value)
                        value = re.sub(r';', r'; ', value)
                        value = re.sub(r' (.*?)=', r' <span class=a>\1</span>=', value)
                        coding_lines.append(nr + ': ' + value)
                # sort lines numerically by coding numbers (coding_9 etc) and join
                coding_lines = sorted(coding_lines, key=lambda x: int(x.split(':')[0]))
                print_codings = '<br/>\n'.join(coding_lines)

                clean = []
                xpos = {}  # store xpos (the original Frantext pos tag in col 5)
                deps = {}  # store id-head relations
                for w in range(len(sentences[s])):  # loop through words in sentence
                    token = sentences[s][w]
                    id = token["id"]
                    deps[id] = token["head"]  # store head node in a dict
                    xpos[id] = token["xpos"]  # store xpos in a dict
                    if re.search(r'^V', token["xpos"]):  # highlight verbs
                        clean.append('<span class=v>' + token["form"] + '</span>')
                    else:
                        clean.append(token["form"])  # for printed plain text
                sprint = " ".join(clean)  # the tokens
                sprint = re.sub(r' ([,:;\.\!\?])', r'\1', sprint)
                sprint = re.sub('\' ', '\'', sprint)
                redirect_stdout_to_buffer()
                trees[s].print_tree()  # get the root of the tree with the same index as the sentence
                tree_str = sys.stdout.getvalue()  # make a list of print_tree objects
                restore_stdout()
                tree_strings.append(tree_str)
                sparsed = tree_to_html(tree_str, xpos, deps)  # convert the tree to HTML and add dependencies

                # print HTML
                printOutput = '\n<a name=\"%s\"></a><hr>\n<h3>%s</h3>\n<font color="Sienna">%s</font>\n%s\n\n<p class="coding">%s</p>\n\n<p><div class=\"parse\"><p>%s</em></p></div>\n' % (sCode, sCode, bib, sprint, print_codings, sparsed)
                out.write(printOutput)

            out.write(htmlFoot + '\n')


    # output coding table as tsv
    outputAll = []
    for key in sorted_keys:
        outputAll.append(codedCorpus[key])
    if args.table != '':   # -t
        writeTable(outputAll)
        print("To concatenate several coding table files preserving only the column header:\n%s" % "  > awk 'FNR==1 && NR!=1 {next} {print}' coded/*.csv > all.csv")
    if args.html:
        print("New HTML files were createed. Don't forget to update them on your server.")

#-------------------------------------------------------
# parse arguments
#-------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
       description='''
In a CoNLL-U file, the script produces coding strings with attribute-value pairs for structural properties.
For example: iobj=pron  for pronominal indirect object
A coding string is produced for each matching governing node in a sentence (i.e. for each clause or predicate).
Coding strings are saved in CoNLL-U metadata format.

''', formatter_class = argparse.RawTextHelpFormatter   # allows triple quoting for multiple-line text
       )
    parser.add_argument('file_name', type=str, help = "input data, a CoNLL-U file")
    parser.add_argument('out_file', type=str,  help='output = CoNLL-U with added coding strings')
    parser.add_argument(
       '-c', '--compare_table', default = "", type = str,
       help='compare this CorpusSearch coding table with the input file (UD codings)')
    parser.add_argument(
        '-f', '--first_rule', action='store_true',
        help='if the first rule for an attribute matches, discard following rules)')
    parser.add_argument(
        '-k', '--keep_target_node_info', action='store_true',
        help='keep target node features (default remove)')
    parser.add_argument(
       '-r', '--request', default = "", type = str,
       help='read GREW requests from this tsv table')
    parser.add_argument(
       '-t', '--table', default = "", type = str,
       help='write coding strings to this tsv table')
    parser.add_argument(
       '--table_empty_string', default = "_", type = str,
       help='fill empty columns with this string')
    parser.add_argument(
       '--json', action='store_true',
       help='print graphs in JSON format instead of CoNLL -- NOT YET IMPLEMENTED')
    parser.add_argument(
       '-C', '--check_ids', action='store_true',
       help='adds sent_id and text to metadata, if missing')
    parser.add_argument(
       '-H', '--html', action='store_true',
       help='creates HTML version of corpus files')
    parser.add_argument(
       '--html_file', default = None, type = str,
       help='special name for HTML file (default: file name = text_id)')
    args = parser.parse_args()
main(args)

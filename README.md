# Process Universal Dependencies (UD)

Extract a coding table of CoNLL-U corpora, similar to what CorpusSearch coding queries do for Penn corpora.

Requires: grewpy, nltk, conllu

Status is work in progress:

- requests not finalized
- requests not fully adapted to HOPS pos categories

## Quick start

If the parsed files are in the sub-folder hopsed:

> cd hopsed;for i in *.conllu; do echo "------- $i"; ~/git/ud-coding/ud-coding.py --html --first_rule --keep_target_node_info -r ~/git/ud-coding/requests.tsv -t ../coded/${i%.*}.csv $i ../coded/${i%.*}.coded.conllu; done; cd ..    


This will

- Add codings to test.conllu, based on requests in requests.tsv
- Write the CoNLL-U  file with added codings to *.coded.conllu
- Write the codings in tabular format, where each attribute is a column
- Write the corpus files in HTML format in subfolder 'ft' and add a URL to the coding file

## History

- 1.7:
    - -H --html creates corpus HTML files in sub-folder 'ft'
    - --html_file <file> creates a single HTML file (e.g. for a smaller sample corpus)
    - --check_ids adds sent_id if not present
- 1.6: more metadata in table (date etc.)
- 1.5: bug fixes
- 1.4: --first_rule   for an attribute, rules following the first matching rule are ignored
- 1.3: --compare_table  compares to coding tables (work in progress)
> ud-coding.py -c cs-codings.csv ud-codings.csv comp-table.csv 

- Version 1.2: first version with adequate speed / memory management

## Install grew (on macos)

Following instructions on <http://grew.fr/usage/install>
The installation of *grewpy* is successful (on macos) only if
everything else was upgraded before (brew, grew etc.).
The doc also explains the installation in Linux.

In order to get the latest versions of grew(py), none of the update or
upgrade steps should be skipped.

### opam and grew

- Update Xcode command-line tools
- Update Homebrew

> brew update
> brew upgrade

- Install opam

> brew install aspcud
> brew install opam

- Install opam (installing the ocam-base-compiler takes seveal minutes)

> opam init
> opam switch create 4.14.1 4.14.1
> eval $(opam env --switch=4.14.1)

- Install grew (also takes a while, installs 57 packages)
  - (if problem when adding the repository, brew upgrade wget)

  > opam remote add grew "http://opam.grew.fr"
  > opam install grew

- Run the following command to use grew in all existing switches, or
  in newly created switches, respectively.
  (I haven't done that in my installation)

  > opam repository add grew --all-switches --set-default

- (optional) Update to a new version of grew and check version
- Nov 2023: grew 1.14.0; grewpy_backend: 0.5.1

  > opam update
  > opam upgrade
  > opam list | grep grew

### install the Python library backend

- install grewpy in opam

> opam update
> opam install grewpy_backend

- add package to python

> pip3 install grewpy

- Test: should display the port (8888 or higher)

> echo "import grewpy" | python3

- Output (after some time): connected to port: 55875 (for example)


## Manipulate CoNLL-U meta data

### Goal:

A process analogous to CorpusSearch coding queries that results
in a coding table, specifying for each clause its syntactic properties
as attribute-value pairs.

Method: a python script using the grewpy package to parse a corpus.

1. Add a coding string to the meta data of the sentence
2. Modify the coding string if a graph matches a condition

For example, if the sentence has an indirect object that is a pronoun, add
iobj:pron (or similar) to the coding string.

CoNLL-U metadata can be manipulated in JSON, using json_data() from the Graph
class, then convert back using to_conll(), like so:

```
print ("Use json_data from Graph class to manipulate meta info:")
print(graph.json_data()["meta"])
graph.json_data()["meta"]["coding"] = "This is my coding string."
print ("We see the new 'coding' attribute in the metadata:")
print(graph.json_data()["meta"])
print ("... and we can print it as conll:")
print(graph.to_conll())
```

### A script that deals with a list or rules

A python script based on the grewpy package for coding one
rule (direct object): ud-coding.py

- takes a CoNLL corpus as input
- reads a table of grew rules that are associated with attribute-value pairs
- matches the rules against the graphs and adds att-val pairs to coding string
- writes the augmented corpus as output (with codings in the meta info of graphs)
- writes the coding strings to a separate tsv table

Call (see more examples below):

> python3 ud-coding.py --first_rule -r requests.tsv test.conllu coded.conllu

### Requests (search rules)

The input file for requests is a table with the following columns,
delimited by tabulators:

1. an attribute-value pair if the form 'att=val'
2. a search pattern (as introduced by the keyword 'pattern' in GREW)
3. (optional) a negative search pattern (as introduced by the keyword 'without' in GREW)

Rows where the first column starts with '#' are treated as comments.

### Compare tables

First run coding command:

> ~/git/ud-coding/ud-coding.py --first_rule --keep_target_node_info -r requests.tsv -t bayart-udcoding.csv hops-parsed/bayart.conllu bayart-coded.conllu

Then compare with CorpusSearch coding:
> ~/git/ud-coding/ud-coding.py -c bayart-cscoding.csv bayart-udcoding.csv cmp-codings.csv


## Parse Frantext public domain texts

### Convert XML to CoNLL using Python 

As source, Use XML files from TXM conversion (by Thomas Rainsford, April/May 2023).
Convert using xml2conll.py

```{bash}
for i in *.xml
    do echo "---------- $i"
    xml2conll.py -s '[\.\?\!\;]' $i > conllu/${i%.*}.conllu || { echo ' - exiting for loop'; break; }
done
```

### Convert XML to CoNLL using XSL (by Tom Rainford)

- download <https://github.com/ILR-Stuttgart/frantexttxm/blob/main/conll/xml-txm_to_conll.xsl>
- On Mac, saxon needs to be installed:

> brew install saxon-b
> java -cp /usr/local/Cellar/saxon-b/9.1.0.8/share/saxon-b/saxon9.jar net.sf.saxon.Transform -xsl:xml-txm_to_conll.xsl 0232.xml include-annotation=yes > 0232.conllu


### Run hopsparser

```{shell}
mkdir hopsed
for i in *.conllu
do 
  echo "--- $i"
  hopsparser parse ../UD_French-Sequoia-flaubert $i > hopsed/$i
done
```

### Add UD coding

Extract coding lines from CoNLL-U files:

```{shell}
mkdir coded
for i in *.conllu
do
  echo "------- $i"
  ~/git/ud-coding/ud-coding.py --first_rule --keep_target_node_info -r ~/git/ud-coding/requests.tsv -t coded/${i%.*}.csv $i coded/${i%.*}.coded.conllu
done
```

Also create HTML corpus files:

```{shell}
cd hopsed
rm ft/index.html
counter=0;
for i in *.conllu
  do ((counter++))
  echo "------- $i (file $counter)"
  ~/git/ud-coding/ud-coding.py --html --first_rule --keep_target_node_info -r ~/git/ud-coding/requests.tsv -t ../coded/${i%.*}.csv $i ../coded/${i%.*}.coded.conllu
done
```

Concatenate the coding tables of the individual files:

```{shell}
cd coded
cat *.csv | head -1 > all.coded   # header line
tail -q -n+2 *.csv >> all.coded   # add tables without header line
mv all.coded all.coded.csv        # rename
```

or more easily using awk:
> awk 'FNR==1 && NR!=1 {next} {print}' coded/*.csv > all.csv

## conllu-sample.py

For each year in metadata (date), collect a sample of sentences.
Default: 10 sentences per sample, min length 12 words (use options to change).

Use Option --restrict <regex> to select sentences containing this regex.

Usage:

1. Collect samples
> python3.11 conllu-sample.py -o ftpub1-sample-per-year.conllu "hopsed/*.conllu" 

2. Apply coding rules

Use '--html_file' to create a single HTML file for these samples

>  ~/git/ud-coding/ud-coding.py --html --html_file ftpub1-sample-per-year.coded.html --first_rule --keep_target_node_info -r ~/git/ud-coding/requests.tsv -t ftpub1-sample-per-year-coded.csv ftpub1-sample-per-year.conllu ftpub1-sample-per-year.coded.conllu

3. Use coding table in conjunction with server-installed HTML corpus file
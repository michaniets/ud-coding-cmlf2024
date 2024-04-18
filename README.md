# Process Universal Dependencies (UD)

Extract a coding table of CoNLL-U corpora, similar to what CorpusSearch coding queries do for Penn corpora.

Requires: grewpy, nltk, conllu

## Documentation

This version is referenced and explained in my paper at "Congrès Mondial de Linguistique française, 2024, Lausanne"

Title: _Réconcilier les formats d'annotation syntaxique pour faciliter l'analyse de la syntaxe française en diachronie_

Check my other repositories for updated versions of the script.


## Quick start

If the parsed files are in the sub-folder hopsed:

````
cd hopsed
for i in *.conllu
do
  echo "------- $i"
  ud-coding.py --html --first_rule --keep_target_node_info -r requests.tsv -t ../coded/${i%.*}.csv $i ../coded/${i%.*}.coded.conllu
done
cd ..    
```

This will

- Add codings to test.conllu, based on requests in requests.tsv
- Write the CoNLL-U  file with added codings to *.coded.conllu
- Write the codings in tabular format, where each attribute is a column
- Write the corpus files in HTML format in subfolder 'ft' and add a URL to the coding file

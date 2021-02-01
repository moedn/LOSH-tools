# LOSH - Tools

This repo contains tools for the [LOSH](https://github.com/OPEN-NEXT/LOSH/) project.

## Install (Python) dependencies

```bash
sudo pip install -r requirements.txt
```

## Tools

### RDF to WikiBase ontology converter

Reads our *osh-metadata.ttl* OKH meta-data ontology file (format: RDF/Turtle),
and converts it to a quasi equivalent ontology on a WikiBase instance
through the *api.php* web interface.
It writes to our OHO WikiBase instance, and cna be used like this:

```bash
python3 rdfont2wb.py 'MyOhoUser' 'MyOhoPasswd'
```

It can be used to create the ontology from scratch,
or to update it - just run it! :-)

### OKH YAML file statistics gatherer

Gathers statistics about the keys used in a bunch of OKH YAML files.
It can be run like this:

```bash
python3 stats_okh1.py
```

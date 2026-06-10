ITERATIONS ?= 100000
HALF_LIFE ?= 10

LEAGUES = PL ELC PD BL1 SA FL1 DED PPL
ELC_ARGS = --top 6 --bottom 3

.PHONY: all fetch reports clean html-only $(LEAGUES)

all: fetch reports

fetch:
	python3 fetch.py $(LEAGUES)

reports: $(LEAGUES) index

PL: data/PL.csv
	python3 plmodel.py --fixtures data/PL.csv --html html/PL-predictions.html \
		--half-life $(HALF_LIFE) --iterations $(ITERATIONS)

ELC: data/ELC.csv
	python3 plmodel.py --fixtures data/ELC.csv --html html/ELC-predictions.html \
		--half-life $(HALF_LIFE) --iterations $(ITERATIONS) $(ELC_ARGS)

PD: data/PD.csv
	python3 plmodel.py --fixtures data/PD.csv --html html/PD-predictions.html \
		--half-life $(HALF_LIFE) --iterations $(ITERATIONS)

BL1: data/BL1.csv
	python3 plmodel.py --fixtures data/BL1.csv --html html/BL1-predictions.html \
		--half-life $(HALF_LIFE) --iterations $(ITERATIONS)

SA: data/SA.csv
	python3 plmodel.py --fixtures data/SA.csv --html html/SA-predictions.html \
		--half-life $(HALF_LIFE) --iterations $(ITERATIONS)

FL1: data/FL1.csv
	python3 plmodel.py --fixtures data/FL1.csv --html html/FL1-predictions.html \
		--half-life $(HALF_LIFE) --iterations $(ITERATIONS)

DED: data/DED.csv
	python3 plmodel.py --fixtures data/DED.csv --html html/DED-predictions.html \
		--half-life $(HALF_LIFE) --iterations $(ITERATIONS)

PPL: data/PPL.csv
	python3 plmodel.py --fixtures data/PPL.csv --html html/PPL-predictions.html \
		--half-life $(HALF_LIFE) --iterations $(ITERATIONS)

index:
	python3 generate_index.py

html-only:
	@for league in $(LEAGUES); do \
		python3 plmodel.py --report data/$$league-predictions.json --html html/$$league-predictions.html; \
	done

clean:
	rm -f data/*-predictions.json html/*.html

ITERATIONS ?= 100000
HALF_LIFE ?= 10

LEAGUES = PL ELC PD BL1 SA FL1 DED PPL
ELC_ARGS = --top 6 --bottom 3

.PHONY: all fetch reports index clean html-only $(LEAGUES)

all: fetch reports

fetch:
	python3 fetch.py $(LEAGUES)

reports: $(LEAGUES) index

# If the CSV is missing or only contains the header row (off-season or fetch
# failure), write an off-season placeholder page and continue instead of erroring.
define run_league
	@if [ ! -s data/$@.csv ] || [ $$(wc -l < data/$@.csv) -le 1 ]; then \
		echo "$@: no fixtures in data/$@.csv — writing off-season placeholder"; \
		python3 write_offseason.py $@; \
	else \
		python3 plmodel.py --fixtures data/$@.csv --html html/$@-predictions.html \
			--half-life $(HALF_LIFE) --iterations $(ITERATIONS) $($@_ARGS); \
	fi
endef

PL ELC PD BL1 SA FL1 DED PPL:
	$(run_league)

index:
	python3 generate_index.py

html-only:
	@for league in $(LEAGUES); do \
		python3 plmodel.py --report data/$$league-predictions.json --html html/$$league-predictions.html; \
	done

clean:
	rm -f data/*-predictions.json html/*.html

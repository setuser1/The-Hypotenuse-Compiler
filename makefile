.PHONY: run install

run: install
	python3 src/main.py $(CURDIR)/test/ex.ctri

install:


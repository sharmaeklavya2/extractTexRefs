INAME = example
TEX_OPTIONS = -cnf-line "max_print_line = 10000" -halt-on-error
default:
	pdflatex $(TEX_OPTIONS) $(INAME).tex
	bibtex $(INAME).aux
	pdflatex $(TEX_OPTIONS) $(INAME).tex
	pdflatex $(TEX_OPTIONS) $(INAME).tex
clean:
	rm -f *.{aux,bbl,blg,log,out,toc,vtc,cut}

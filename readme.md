# extractTexRefs

`extractTexRefs.py` extracts information about citations, theorems, definitions, sections, etc. from the LaTeX aux file.

## Example

Suppose the second theorem in a TeX file is this:

```tex
\begin{theorem}
\label{odd-sq-is-odd}
The square of an odd number is also odd.
\end{theorem}
```

Then its entry in the `.aux` file will look something like this:

```tex
\newlabel{odd-sq-is-odd}{{2}{1}{}{theorem.6}{}}
```

`extractTexRefs.py` parses it and outputs this JSON:

```json
{"type": "theorem", "texLabel": "odd-sq-is-odd", "outputId": "2", "anchor": "theorem.6", "page": "1"}
```

A more complete example can be found in the `example` directory.
Running the following commands will build `example/example.tex`
and extract information about definitions, theorems, lemmas, sections, etc.

```
cd example
make
cd ..
python3 extractTexRefs.py example/example.aux
```

## How it works

Corresponding to each `\label` command in a TeX file, there is a line in the `.aux` file of the following format:

```\newlabel{texLabel}{{outputId}{page}{context}{anchor}{misc}}```

There are addition lines if `\cite` commands are used
or the [`cleveref`](https://ctan.org/pkg/cleveref) package is used.

`extractTexRefs.py` parses these and outputs a JSON list of all these references.

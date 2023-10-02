# Sphinx AutoDoc
This README provides documentation for Sphinx AutoDoc, a tool for generating documentation from Python docstrings.

## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
- [Contact Information](#contact-information)


## Installation
To install Sphinx AutoDoc, you can use pip:

```bash
pip install sphinx
```

## Usage

A good video for reference:
https://www.youtube.com/watch?v=BWIrhgCAae0


**Step 1: Create docs folder in project directory**
```bash
Mkdir docs
```

**Step 2: Go into newly created folder, and setup your Project with Quickstart**

Quickstart will quickly generate a basic configuration file and directory structure for your documentation.

To use Quickstart:
```bash
sphinx-quickstart
```

Quickstart will ask you a number of questions that will determine it’s actions. You can generally accept the default values. After the program has run, you’ll notice three new files in docs folder: conf.py, index.rst, and Makefile.

Below is an example:

```
Welcome to the Sphinx 7.0.1 quickstart utility.

Please enter values for the following settings (just press Enter to
accept a default value, if one is given in brackets).

Selected root path: .

You have two options for placing the build directory for Sphinx output.
Either, you use a directory "_build" within the root path, or you separate
"source" and "build" directories within the root path.
> Separate source and build directories (y/n) [n]: 

The project name will occur in several places in the built documentation.
> Project name: citations_finder
> Author name(s): J. Russack, S. Zhang
> Project release []: 

If the documents are to be written in a language other than English,
you can select a language here by its language code. Sphinx will then
translate text that it generates into that language.

For a list of supported codes, see
https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-language.
> Project language [en]: 

Creating file /Users/Sophiaaa/Documents/CalAcademy/citations_finder/docs/conf.py.
Creating file /Users/Sophiaaa/Documents/CalAcademy/citations_finder/docs/index.rst.
Creating file /Users/Sophiaaa/Documents/CalAcademy/citations_finder/docs/Makefile.
Creating file /Users/Sophiaaa/Documents/CalAcademy/citations_finder/docs/make.bat.

Finished: An initial directory structure has been created.

You should now populate your master file /Users/Sophiaaa/Documents/CalAcademy/citations_finder/docs/index.rst and create other documentation
source files. Use the Makefile to build the docs, like so:
   make builder
where "builder" is one of the supported builders, e.g. html, latex or linkcheck.
```

**Step 3: Write your docstrings**

Sphinx provides a template that makes your life easier. To create a docstring template for a module, use Cmd + shift + 2 on Mac.

Example template:

    ```
    _summary_

    :return: _description_
    :rtype: _type_
    ```

Filled template or completed docstring:

    ```
    executes query to retrieve rows from two tables - 
    matches, and doi - and keeps the row if doi exists in both 
    table and 'ignore' column in 'matches' table is 0.

    :return: The query results containing matched rows.
    :rtype: list
    ```


**Step 4: Adjusting the conf.py File**

Get out of docs folder to Project folder, then run:

```bash
sphinx-apidoc -o docs .
```

Open conf.py, and:

 * Change ```html_theme = 'sphinx_rtd_theme'```

 * Change extensions to ```extensions = ["sphinx.ext.todo", "sphinx.ext.viewcode", "sphinx.ext.autodoc"]```

 * Add at top of file:
 ```
 import os
 import sys
 sys.path.insert(0,os.path.abspath(".."))
 ```

**Step 5: Generate your Docs!**

Change directory to docs folder, and run the following:
```bash
Make html
```

## Contact Information

For questions, please email Sophia Zhang at sophiafr17@gmail.com 
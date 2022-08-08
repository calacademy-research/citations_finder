# Installation
## 1. Create and activate a virtual environment
### If you want to use Conda:
Install Miniconda: https://docs.conda.io/en/latest/miniconda.html

Then, type in the following commands in your terminal:
```
$ conda create --name <whatever-name-you-want>
$ conda activate <whatever-name-you-want>
```

**Resource for Conda:** https://docs.conda.io/projects/conda/en/4.6.0/_downloads/52a95608c49671267e40c689e0bc00ca/conda-cheatsheet.pdf 

## 2. Install pipreqs
In your terminal with the environment activated, type in the command:
```
$ pip install pipreqs
```
\* Try pip3 if pip doesn't work

## 3. Use requirements.txt to install packages
In your terminal with the environment activated, type in the command:
```
$ pip install -r requirements.txt
```

## 4. Set up config.ini file
Copy the contents of config.template.ini into a new file called config.ini and modify to fit your needs

## Notes
* For VSCode, make sure your Python interpreter is set to the path of your environment before running. You can check the by opening the Command Palette (Ctrl or Cmd + Shift + P) and clicking 'Python: Select Interpreter'. Click the refresh button if you don't see the environment path you created. 

## FAQ/troubleshooting.

  I'm getting "[SSL: CERTIFICATE_VERIFY_FAILED]"! Take a look at page 49, here: https://ncbi-taxonomist.readthedocs.io/_/downloads/en/stable/pdf/
  
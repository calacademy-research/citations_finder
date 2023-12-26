The Problem:

Unlike paper citations, there is no systematic tracking of references to museum collections. Identifying
specimen references has historically been labor-intensive, requiring either manual reading or reporting by
researchers back to the institutions they worked with. This process is error-prone and unreliable.

Research specimens are typically numbered by a scheme local to each institution's individual collection. At
CAS, we identify specimens with a collection ID and a number. "CASIZ" for invertebrate zoology and "CASENT"
for entomology are examples, but we also – and most commonly – use the simple acronym "CAS". This overlapping
use of acronyms is problematic, as "CAS" is also used by the Chinese Academy of Sciences, "Institute of Botany
CAS" (Czech Academy of Sciences), and it is the name of several proteins of interest and numerous chemical
formulae. As a result, it is challenging to identify these specimens with a simple word match. Moreover, the
relevant papers aren't open access, so there's no easy way to text search the bodies of these papers for
potential matches. Institutions like Google and Microsoft Academic can afford to subscribe to and data mine
extensive bodies of literature to generate their reference graphs. They further benefit from standard methods
of formatting paper references that are easy to parse and link.

The Data Ecosystem:

GBIF: A digital specimen repository with sophisticated APIs. They provide the GBIF literature
search (https://www.gbif.org/developer/literature), which offers a simple search mechanism to look for
acronyms of interest. While not sufficient for the sophisticated text matching required to trace specimens
back to collections, it's an excellent resource for finding journals of interest.

CROSSREF: Supplies an excellent API that makes paper metadata available. These data include a mapping of ISSNs
to DOIs (Digital Object Identifiers) for every paper published in each journal.

UNPAYWALL: Links DOIs to URLs for papers that are open source.

By integrating these tools and improving our tracking methods, we can significantly enhance the accuracy and
efficiency of referencing museum collections in scientific literature.

The Process:

Identify Journals of Interest:

Add journals directly to "journals.tsv" or extract them using the utilities built into this program. Control
this process through the "Journal Population" section in "config.ini".
Populate the Database:

Once the journals are identified, populate the database with their DOIs and metadata from CROSSREF.
Download Papers:

Download as many papers as is practical, considering your resource limitations.
Scan for References:

Scan the papers for possible references using a text-matching heuristic. Refer to "config.ini" and "readme.md"
for detailed configuration instructions.
Manual Review:

Manually review the scan results to ensure accuracy and relevance.
Extract Relevant Information:

Copy out relevant papers and list the identified possible references.
Configuring and Running:

Most documentation is embedded in "config.template.ini". For more detailed notes, consult "README.md".
It is recommended to run one step at a time with manual supervision, as this is a weeks-long process.
Downloading the DOIs alone can take up to three days for a large collection of journals. Scoring, although
relatively quick, requires careful attention.
This process is designed to ensure thorough and accurate identification of references in scientific
literature, albeit time-consuming and requiring meticulous manual oversight.



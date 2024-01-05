# Use a base image with Python and Firefox
FROM ubuntu:22.04
# Set the timezone to Pacific Standard Time (PST)
ENV TZ=America/Los_Angeles
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone


# Install Python and pip
USER root
RUN apt-get update && \
    apt-get install -y python3 python3-pip rsync default-libmysqlclient-dev wget ca-certificates tar gzip libgtk-3-0 libasound2 libdbus-glib-1-2 libgtk-3-0 libxrender1 libxcomposite1 libxt6 libpci3 libpulse0 libpangocairo-1.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Download and install Firefox 121.0
RUN wget -q "https://ftp.mozilla.org/pub/firefox/releases/121.0/linux-x86_64/en-US/firefox-121.0.tar.bz2" -O /tmp/firefox.tar.bz2 && \
    tar -xjf /tmp/firefox.tar.bz2 -C /opt && \
    rm /tmp/firefox.tar.bz2 && \
    ln -s /opt/firefox/firefox /usr/local/bin/firefox

# Download and install GeckoDriver (replace 'v0.33.0' with the version compatible with Firefox 121.0)
RUN wget -q "https://github.com/mozilla/geckodriver/releases/download/v0.33.0/geckodriver-v0.33.0-linux64.tar.gz" -O /tmp/geckodriver.tar.gz && \
    tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin && \
    rm /tmp/geckodriver.tar.gz

# Install OpenJDK 11
RUN apt-get update && \
    apt-get install -y openjdk-11-jdk && \
    rm -rf /var/lib/apt/lists/*

# Set the JAVA_HOME environment variable
ENV JAVA_HOME /usr/lib/jvm/java-11-openjdk-amd64


# Set the working directory in the container
WORKDIR /app

# Copy the Python requirements file into the container
COPY requirements.txt /app

# Install Python dependencies
RUN pip install -r requirements.txt

# Copy the application code into the container
# Assuming all your code is in the current directory (citations_finder)
# Copy the specified files into the container
COPY collection_base.py /app/
COPY config.py /app/
COPY copyout.py /app/
COPY crossref_journal_entry.py /app/
COPY database_report.py /app/
COPY database_scan.py /app/
COPY db_connection.py /app/
COPY doi_database.py /app/
COPY doi_entry.py /app/
COPY downloader.py /app/
COPY downloaders.py /app/
COPY journal_finder.py /app/
COPY known_good_papers.py /app/
COPY main.py /app/
COPY scan.py /app/
COPY scan_database.py /app/
COPY unpaywall_downloader.py /app/
COPY utils_mixin.py /app/
COPY validator.py /app/

# Command to run the application
CMD ["python3", "main.py"]

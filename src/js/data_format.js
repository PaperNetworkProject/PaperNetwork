function Paper(JSON_DATA){
    this.id =               JSON_DATA.id;
    this.pmid =             JSON_DATA.pmid;
    this.doi =              JSON_DATA.doi;
    this.title =            JSON_DATA.title;
    this.authors =          JSON_DATA.authorString;
    this.pub_year =         JSON_DATA.pubYear;
    this.citation_count =   JSON_DATA.citedByCount;
    return this;
}
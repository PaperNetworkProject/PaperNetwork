class LtdPaperDetails:
    """  """
    # --- --- --- --- --- --- --- ---
    def _get_id_(self):
        return self.__id
        
    def _set_id_(self, id):
        if not isinstance(id, str):
            raise TypeError("self.__id : str expected, %s found" % type(id).__name__)
        self.__id = id
    
    id = property(_get_id_, _set_id_)
    # --- --- --- --- --- --- --- ---
    def _get_src_(self):
        return self.__src
        
    def _set_src_(self, src):
        if not isinstance(src, str):
            raise TypeError("self.__src : str expected, %s found" % type(src).__name__)
        self.__src = src
        
    src = property(_get_src_, _set_src_)
    # --- --- --- --- --- --- --- ---
    def _get_title_(self):
        return self.__title
        
    def _set_title_(self, title):
        if not isinstance(title, str):
            raise TypeError("self.__title : str expected, %s found" % type(title).__name__)
        self.__title = title
        
    title = property(_get_title_, _set_title_)
    # --- --- --- --- --- --- --- ---
    def _get_authors_(self):
        return self.__authors
        
    def _set_authors_(self, authors):
        if not isinstance(authors, list):
            raise TypeError("self.__authors : [str] expected, %s found" % type(authors).__name__)
        for author in authors:
            if not isinstance(author, str):
                raise TypeError("self.__authors : [str] expected, [%s] found in the list" % type(author).__name__)
        self.__authors = authors
        
    authors = property(_get_authors_, _set_authors_)
    # --- --- --- --- --- --- --- ---
    def _get_pubYear_(self):
        return self.__pubYear
        
    def _set_pubYear_(self, pubYear):
        if not isinstance(pubYear, int):
            raise TypeError("self.__pubYear : int expected, %s found" % type(pubYear).__name__)
        self.__pubYear = pubYear
        
    pubYear = property(_get_pubYear_, _set_pubYear_)
    # --- --- --- --- --- --- --- ---
    def _get_citedCount_(self):
        return self.__citedCount
        
    def _set_citedCount_(self, citedCount):
        if not isinstance(citedCount, int):
            raise TypeError("self.__citedCount : int expected, %s found" % type(citedCount).__name__)
        self.__citedCount = citedCount
    
    citedCount = property(_get_citedCount_, _set_citedCount_)
    # --- --- --- --- --- --- --- ---
    
    def __init__(self, id = "", src = "", title = "", authors = [], pubYear = -1, citedCount = -1):
        self.id = id                  # type : string
        self.src = src                # type : string
        self.title = title            # type : string
        self.authors = authors        # type : [string]
        self.pubYear = pubYear        # type : int
        self.citedCount = citedCount  # type : int

    def __str__(self):
        return "[ id : {0}, title : {1}, year : {2}, citations {3}]".format(self.__id, self.__title, str(self.__pubYear), str(self.__citedCount))
        
    def __eq__(self, other):
        return self.__id == other.__id # compare two papers using their IDs
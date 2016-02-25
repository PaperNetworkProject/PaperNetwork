/*** GLOBAL VARIABLES ***/
 var API_endpoint = "http://www.ebi.ac.uk/europepmc/webservices/rest/";
 var word_separator = "&20";

/*** ENTRY POINT ***/
$(document).ready(function(){
    var array_search = ["malaria","treatment"];
    var string_search = "malaria";
    //search(array_search, false);
    search(string_search, false, true);
});
 
/*** FUNCTIONS ***/
function formatSearchTerms(search_terms){
    if (Array.isArray(search_terms))
        return formatArraySearchTerms(search_terms);
    else if (typeof search_terms === 'string' || search_terms instanceof String)
        return formatStringSearchTerms(search_terms);
}

function formatArraySearchTerms(search_terms){
    var formated_search_terms = "";
    for (var i = 0; i < search_terms.lenght; i++){
        if (i != 0) formated_search_terms += word_separator;
        formated_search_terms += search_terms[i];
    }
    return formated_search_terms;
}

function formatStringSearchTerms(search_terms){
    return search_terms.replace(" ", word_separator);
}

function countNumberOfPages(JSON_query_result, results_per_page){
    var hit_count = JSON_query_result.hitCount;
    var string_number = "" + (hit_count/results_per_page);
    return parseInt(string_number) + 1;
}

function search(search_terms, async, referenced_only){
    async = async || true;
    referenced_only = referenced_only || false;
	if (!async) $.ajaxSetup({async:false});
    var search_result = [];
    // format the query
    var result_per_query = 1000;
    var formated_search_terms = formatSearchTerms(search_terms);
    var query = API_endpoint + "search?query=" + formated_search_terms + "&pageSize="+result_per_query+"&format=json";
    // Perform the queries
    $.get(query, function(query_data,status){
        var number_of_pages = countNumberOfPages(query_data, result_per_query);
        for (var i in query_data.resultList.result){
            var object = query_data.resultList.result[i];
            if (object.hasReferences != "N" || !referenced_only) search_result.push(new Paper(object));
        }
        
		for (var i = 2; i < number_of_pages; i++){
			$.get(query+"&page="+i, function(query_data2,status){
				for (var i in query_data.resultList.result){
                    var object = query_data.resultList.result[i];
                    if (object.hasReferences != "N" || !referenced_only) search_result.push(new Paper(object));
                }
                console.log("objects produced:");
                console.log(search_result);
			});
		}
	});
    
    if (!async) $.ajaxSetup({async:true});
    
}

/*
$(document).ajaxStart(function(){
    $("#result").css("background-image", "block");
});

$(document).ajaxComplete(function(){
    $("#result").css("display", "none");
});*/
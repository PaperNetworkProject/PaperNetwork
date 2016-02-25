/** counts the number of papers for wich the API gives reference informations
 * Input: the JSON response of a 'search' query
 * Output: the number of papers in the response that have reference informations
 * */
function countReferences(data){
	var count =0;
	$.each(data.resultList.result,function (key,val){
			if(val.hasReferences!="N"){
				count++;
			}
	});
	return count;
}
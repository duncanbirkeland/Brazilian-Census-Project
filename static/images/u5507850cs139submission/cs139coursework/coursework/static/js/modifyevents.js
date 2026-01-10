$(document).ready(function(){   
    $.getJSON('/events.json', function(data){
        var searchbar = $('#searchbar');
        var dropdown = $('#dropdownmenu');
        var totalcapacity = $('#changecapacity');
        $('#addsubmitbutton').on('click', function(event){
            event.preventDefault();
            $('#submitimage').attr('enctype','multipart/form-data');
            $('#submitimage').submit();
            //For some reason the enc attached to my form doesn't function by default so I add the attribute again before the form submits
        })
        function showdropdown(values){      
            dropdown.html('');
            values.forEach(function(value) {
                const div = $('<div></div><br>');
                div.text(value.name); 
                div.on('click',function() {
                    searchbar.val(value.name);
                    $('#changecapacity').val(value.capacity);
                    //Sets the capacity field to be the capacity of the item searched
                    $('#cancelid').val(value.id);
                    $('#modifyid').val(value.id);
                    //Set hidden input boxes to have the id of the event

                    dropdown.hide(); 
                });
                dropdown.append(div);
            });
            if (values.length === 0) {
                dropdown.html('<div>No suggestions</div><br>');
                //Show no suggestions if there are no items that fit this query
            }
            dropdown.show();
        }
        
        searchbar.on('input', function(){
            var input = $(this).val().trim().toLowerCase(); 
            if (input == ''){
                dropdown.hide();
                return;
            }
            var items = data.filter(function(item){
                return item.name.toLowerCase().includes(input); 
                //Returns the function to show all items based on the pure form of the input
            });
            showdropdown(items.slice(0,2));
            //Only show 2 search results
        });
    });
}); 
$(document).ready(function(){
    $("body").addClass("continuous");
    if ($("#geterror").val() != "None"){
        alert($("#geterror").val());
    }
    //Sets the body to be a repeating image as this body will continuously scroll with new events
    var hiddenvar = $('#loggedin');

    if (hiddenvar.val() == 0 ){
        $(".submitbutton").val("Please sign in to receive tickets");
        $(".submitbutton").prop('disabled', true);
        //If the user is not logged in, set all buttons to say that you need to sign in and then disable all these buttons
    }

    $(".flex-box").each(function() {
        var button = $(this).find('#ticketbutton')
        //Get the submit button for all flex-boxes
        if ($(this).find('#iscancelled').val() == 1) {
            $(this).find(".submitbutton").val("This event has been cancelled").prop('disabled', true).css("background-color", "lightblue")
            // Set the button to be disabled if the event has been cancelled and change the colour of the button to a new colour
        }

        if ($(this).find("#hasticket").val() == 1){
            var ticketbutton = $(this).find("#ticketbutton")
            //Get the ticket if the user has a ticket for this event
            if ($(this).find('#iscancelled').val() == 0){
        
                ticketbutton.attr('formaction', '/viewticket');
                ticketbutton.attr('value', 'View Ticket');
                ticketbutton.removeClass('submitbutton');
                ticketbutton.addClass('ticketbutton');  
                //If the event is not cancelled set the button to be a viewticket button which will change the route to allow the user to view their ticket

                $(this).append('<br> <form action="/removeticket" method="POST">' +
                '<input type="hidden" value ="' + $(this).find("#eventid").val() +'"name = "getevent">'+
                '<input type="submit" class = "ticketbutton" id ="makeitcoral" value="Remove Ticket">' +
                '</form>');
                //Adds a remove ticket button with a new form with a hidden value to allow the removeticket route to get the event to be removed
                $(this).css('min-height', '85vh')
                //Increase the size of the flex-box as there is a new button
            }
        }

    });
    

    $.getJSON('/events.json', function(data){
        //Gets the JSON file
        var searchbar = $('#flexeventbar');
        var dropdown = $('#dropdownmenuflex');
        data.forEach(function(element) {
            var capacity = $("#"+element.id+ "capacity");
            totalcapacity = element.capacity;
            ticketsallocated = element.tickets_allocated;
            //Sets variables from the JSON File

            if (totalcapacity == ticketsallocated){
                capacity.text("Full");
                capacity.closest('.flex-box').find('.submitbutton').val("No more tickets are available").prop('disabled', true).css("background-color", "lightblue");
                //If the event is full show to the user it's full by changing the submit colour, saying the capacity is full, and disabling the submit button
            }

            else if (ticketsallocated >= totalcapacity *0.95){
                if (totalcapacity - ticketsallocated == 1){
                    capacity.text("Last ticket available");
                }
                else{
                    capacity.text("Last "+ totalcapacity- ticketsallocated + " spaces")
                }
                //If there are less than 5% tickets remaining alert the user to exactly how many tickets are left
                
            }   
            else{
                capacity.text("Plenty remain");
            }
            //Otherwise tell the user that there are plenty of tickets left

        })
        function showdropdown(values){      
            dropdown.html('');
            //Sets the dropdown to be blank initially
            values.forEach(function(value) {
                const div = $('<div></div><br>');
                //Creates an empty div for the dropdownmenu
                div.text(value.name); 
                div.on('click',function() {
                    searchbar.val(value.name);
                    dropdown.hide();
                    $(".flex-box").hide();
                    $(".flex-box").filter(function(){
                        return $(this).find('h2').text() === value.name;
                    }).show();
                    //Once an item in the dropdown has been clicked, set the searchbar to be the item clicked and show only the event searched for
                });
                dropdown.append(div);
                //Add this div to the dropdown
            });
            if (values.length === 0) {
                dropdown.html('<div>No suggestions</div><br>');
                //If there are no items that fit this, show no suggestions in the dropdown menu
            }
            dropdown.show();
        }
        
        searchbar.on('input', function(){
            var input = $(this).val().trim().toLowerCase(); 
            if (input == ''){
                dropdown.hide();
                $(".flex-box").show();
                return;
                //If there is nothing in the input show all the flex-boxes
            }
            var items = data.filter(function(item){
                return item.name.toLowerCase().includes(input); 
                //Show only the items that include the text
            });
            showdropdown(items.slice(0,2));
            //Show only the first two items
        });
    });
}); 
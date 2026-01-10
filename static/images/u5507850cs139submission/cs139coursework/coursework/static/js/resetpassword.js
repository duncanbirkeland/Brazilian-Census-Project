$(document).ready(function() {
    $('#sendemail').click(function() {
        var user = $('#enteredemail').val();
        $("#hiddenname").val(user); 
        //Get the email the user has entered, sets a hidden variable to be equal to this to be used later in a form
        $.ajax({
            url: '/sendemail',
            //Performs an ajax request to the route /sendemail
            method: 'POST',
            data: 
                {usertosend: user}
                //Sends the users email to this route
            ,
            dataType: "text",
            success: function(response) {
            },
            error: function(error) {
            }
        });
    });
});
var uid = Args.uid;
var time  = API.messages.getLastActivity({"user_id": uid});
return time.time; 

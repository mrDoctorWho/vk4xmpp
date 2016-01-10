var users = Args.users;
var photoSize = Args.size;
var data = API.users.get({"user_ids":users, fields:[photoSize]});
var len = data.length;
var photos = {};

while (len >= 0) {
    var thisone = data[len];
    if (thisone.id) {
        var id = thisone["id"];
        var size = thisone[photoSize];
        photos.push({"uid": id, "photo":size});
        
    }
    len = len - 1;
}
return photos;
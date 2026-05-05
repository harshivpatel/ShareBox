'use strict';

// import firebase
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.22.2/firebase-app.js";
import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut } from "https://www.gstatic.com/firebasejs/9.22.2/firebase-auth.js"


const firebaseConfig = {
  apiKey: "AIzaSyBSLiR9Xv1ShuZ_FtqtFUFro5CCuCD5nuA",
  authDomain: "sharebox-ad3ba.firebaseapp.com",
  projectId: "sharebox-ad3ba",
  storageBucket: "sharebox-ad3ba.firebasestorage.app",
  messagingSenderId: "614113561043",
  appId: "1:614113561043:web:80efa0c5f06e06ba2ec726",
  measurementId: "G-6L7X7Y2548"
};

window.addEventListener("load", function() {
    const app = initializeApp(firebaseConfig);
    const auth = getAuth(app);
    updateUI(document.cookie);

    // signup of a new user to firebase
    document.getElementById("sign-up").addEventListener('click', function() {
        const email = document.getElementById("email").value
        const password = document.getElementById("password").value

        createUserWithEmailAndPassword(auth, email, password)
        .then((userCredential) => {
            // we have a created user
            const user = userCredential.user;
            
            // get the id token for the user who just logged in and force a redirect to /
            user.getIdToken().then((token) => {
                document.cookie = "token=" + token + ";path=/;SameSite=Strict";
                window.location = "/";
            });

        })
        .catch((error) => {
            // issue with signup that we will drop to console
            console.log(error.code + error.message);
        })
    });

    // login of a user to firebase
    document.getElementById("login").addEventListener('click', function() {
        const email = document.getElementById("email").value
        const password = document.getElementById("password").value

        signInWithEmailAndPassword(auth, email, password)
        .then((userCredential) => {
            // we have a signed in user
            const user = userCredential.user;
            
            // get the id token for the user who just logged in and force a redirect to /
            user.getIdToken().then((token) => {
                document.cookie = "token=" + token + ";path=/;SameSite=Strict";
                window.location = "/";
            });

            
        })
        .catch((error) => {
            // issue with signup that we will drop to console
            console.log(error.code + error.message);
        })
    });

    // signout from firebase
    document.getElementById("sign-out").addEventListener('click', function() {
        signOut(auth)
        .then((output) => {
            // remove the ID token for the user and force a redirect to /
            document.cookie = "token=;path=/;SameSite=Strict";
            window.location = "/";
        })
        
    });
});

// function that will update the UI for the user depending on if they are logged in or not by checking the passed in cookie
// that contains the token
function updateUI(cookie) {
    var token = parseCookieToken(cookie);
    
    // if a user is logged in then disable the email, password, signup, and login UI elements and show the signout button and vice versa
    if(token.length > 0) {
        document.getElementById("login-box").hidden = true;
        document.getElementById("sign-out").hidden = false;
    } else {
        document.getElementById("login-box").hidden = false;
        document.getElementById("sign-out").hidden = true;
    }
};

// function that will take the and will return the value associated with it to the caller
function parseCookieToken(cookie) {
    // split the cookie out on the basis of the semi colon
    var strings = cookie.split(';');

    // go through each of the strings
    for (let i = 0; i < strings.length; i++) {
        // split the string based on the = sign. if the LHS is token then return the RHS immediately
        var temp = strings[i].split('=');
        if(temp[0] == "token")
            return temp.slice(1).join('=');
    }
    
    // if we got to this point then token wasn't in the cookie so return the empty string
    return "";

};
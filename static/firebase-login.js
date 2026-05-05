'use strict';

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

// Maps Firebase error codes to human readable messages
function getErrorMessage(code) {
    const errors = {
        'auth/invalid-email':           'Please enter a valid email address.',
        'auth/user-disabled':           'This account has been disabled.',
        'auth/user-not-found':          'No account found with this email.',
        'auth/wrong-password':          'Incorrect password. Please try again.',
        'auth/email-already-in-use':    'An account with this email already exists.',
        'auth/weak-password':           'Password must be at least 6 characters.',
        'auth/too-many-requests':       'Too many attempts. Please try again later.',
        'auth/network-request-failed':  'Network error. Check your connection.',
        'auth/invalid-credential':      'Invalid email or password.',
    };
    return errors[code] || 'Something went wrong. Please try again.';
}

function showError(message) {
    const el = document.getElementById("auth-error");
    if (el) {
        el.textContent = message;
        el.style.display = "block";
    }
}

function clearError() {
    const el = document.getElementById("auth-error");
    if (el) {
        el.textContent = "";
        el.style.display = "none";
    }
}

function validateInputs(email, password) {
    if (!email || email.trim() === '') {
        showError('Please enter your email address.');
        return false;
    }
    if (!password || password.trim() === '') {
        showError('Please enter your password.');
        return false;
    }
    if (password.length < 6) {
        showError('Password must be at least 6 characters.');
        return false;
    }
    return true;
}

window.addEventListener("load", function() {
    const app = initializeApp(firebaseConfig);
    const auth = getAuth(app);
    updateUI(document.cookie);

    document.getElementById("sign-up").addEventListener('click', function() {
        clearError();
        const email = document.getElementById("email").value;
        const password = document.getElementById("password").value;

        if (!validateInputs(email, password)) return;

        createUserWithEmailAndPassword(auth, email, password)
        .then((userCredential) => {
            const user = userCredential.user;
            user.getIdToken().then((token) => {
                document.cookie = "token=" + token + ";path=/;SameSite=Strict";
                window.location = "/";
            });
        })
        .catch((error) => {
            showError(getErrorMessage(error.code));
            console.log(error.code + error.message);
        });
    });

    document.getElementById("login").addEventListener('click', function() {
        clearError();
        const email = document.getElementById("email").value;
        const password = document.getElementById("password").value;

        if (!validateInputs(email, password)) return;

        signInWithEmailAndPassword(auth, email, password)
        .then((userCredential) => {
            const user = userCredential.user;
            user.getIdToken().then((token) => {
                document.cookie = "token=" + token + ";path=/;SameSite=Strict";
                window.location = "/";
            });
        })
        .catch((error) => {
            showError(getErrorMessage(error.code));
            console.log(error.code + error.message);
        });
    });

    document.getElementById("sign-out").addEventListener('click', function() {
        signOut(auth)
        .then(() => {
            document.cookie = "token=;path=/;SameSite=Strict";
            window.location = "/";
        });
    });
});

function updateUI(cookie) {
    var token = parseCookieToken(cookie);
    if(token.length > 0) {
        document.getElementById("login-box").hidden = true;
        document.getElementById("sign-out").hidden = false;
    } else {
        document.getElementById("login-box").hidden = false;
        document.getElementById("sign-out").hidden = true;
    }
}

function parseCookieToken(cookie) {
    var strings = cookie.split(';');
    for (let i = 0; i < strings.length; i++) {
        var temp = strings[i].split('=');
        if(temp[0] == "token")
            return temp.slice(1).join('=');
    }
    return "";
}
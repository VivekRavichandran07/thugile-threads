# Thugile & Threads for Android

This Android project opens the live storefront as a Trusted Web Activity. The
website's accounts, catalog, cart, Cashfree checkout, shipping rates and order
history use the same backend. The app requires an internet connection.

## Build and test

Open the `android` folder in Android Studio. Use JDK 17 and install Android SDK
Platform 36 and Build Tools 35.0.0. The included wrapper downloads Gradle 8.13.
Run `./gradlew :app:assembleDebug` in WSL or `.\gradlew.bat :app:assembleDebug`
in PowerShell from this folder. The test APK is at
`app/build/outputs/apk/debug/app-debug.apk`. On a connected Android device, use
`adb install -r app/build/outputs/apk/debug/app-debug.apk` or Android Studio's Run
button.

Test Google sign-in, cart and saved addresses, and Cashfree checkout and return
on an Android device. Use a Cashfree sandbox storefront for test payments.

## Verify the domain for full-screen launch

1. Build a signed APK for distribution or a signed Android App Bundle for
   Google Play using Android Studio's Generate Signed Bundle / APK action.
2. Get the SHA-256 fingerprint of the certificate that signs the installed APK.
   For Google Play builds, use the **app signing certificate** shown in Play
   Console. For sideloaded builds, use the certificate that signed the APK.
3. Deploy the Flask code containing the Digital Asset Links endpoint, then set
   `ANDROID_APP_SIGNING_SHA256` on the Railway service to the colon-separated
   fingerprint. Multiple approved certificates can be comma-separated.
4. Check that `https://thugilethreads.store/.well-known/assetlinks.json` returns
   the package name `store.thugilethreads.app` and the expected fingerprint.

Until the domain is verified, a supported Android browser opens the storefront
in a Custom Tab with a browser bar. Keep release signing keys outside the
repository.

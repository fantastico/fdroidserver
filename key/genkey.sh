#!/bin/sh
keytool -genkey -v -keystore fdroid.keystore -alias fdroid -keyalg RSA -keysize 2048 -validity 10000

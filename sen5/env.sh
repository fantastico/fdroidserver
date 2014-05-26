#!/bin/sh

#M2_HOME="/usr/local/apache-maven-3.1.1"
MONGO_ROOT=/home/public/users/huangwenxi/prog/mongodb-linux-x86_64-2.6.1/bin

NDKROOT=/home/public/users/lijiyang/android/android-ndk-r9c
ANDROID_HOME=/home/public/users/lijiyang/android/android-sdk-linux
ANDROID_NDK=/home/public/users/lijiyang/android/android-ndk-r9c
FDROIDROOT=//home/public/users/lijiyang/appstore/fdroidserver
ANDROID_TOOL_HOME=/home/public/users/lijiyang/android/android-sdk-linux/tools
ANDROID_PLATFORM_TOOL_HOME=/home/public/users/lijiyang/android/android-sdk-linux/platform-tools

export PATH=$ANDROID_PLATFORM_TOOL_HOME:$ANDROID_TOOL_HOME:$NDKROOT:$FDROIDROOT:$MONGO_ROOT:$PATH

# The following lines of boilerplate have to be in your project's
# CMakeLists in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.5)

# sdkconfig.defaults git'e girer (placeholder değerler içerir, güvenli).
# sdkconfig.defaults.local .gitignore'da - gerçek WiFi şifreleri SADECE burada,
# hiçbir zaman commit edilmez. Dosya yoksa (henüz oluşturulmadıysa) sorun olmaz.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/sdkconfig.defaults.local")
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults;sdkconfig.defaults.local")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(active-sta)
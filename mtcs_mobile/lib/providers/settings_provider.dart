import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mtcs_mobile/api/api_service.dart';

class SettingsProvider extends ChangeNotifier {
  String _baseUrl = "http://10.0.2.2:9600";

  String get baseUrl => _baseUrl;

  SettingsProvider() {
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString('baseUrl') ?? "http://10.0.2.2:9600";
    ApiService.setBaseUrl(_baseUrl);
    notifyListeners();
  }

  Future<void> updateBaseUrl(String newUrl) async {
    _baseUrl = newUrl;
    ApiService.setBaseUrl(newUrl);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('baseUrl', newUrl);
    notifyListeners();
  }
}

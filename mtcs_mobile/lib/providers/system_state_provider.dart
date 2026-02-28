import 'package:flutter/material.dart';

class SystemStateProvider extends ChangeNotifier {
  String _status = "DISCONNECTED";
  String _lastUpdate = "";

  String get status => _status;
  String get lastUpdate => _lastUpdate;

  void updateState(String newStatus, String updateTime) {
    _status = newStatus;
    _lastUpdate = updateTime;
    notifyListeners();
  }
}

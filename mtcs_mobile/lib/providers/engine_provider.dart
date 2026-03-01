import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:mtcs_mobile/api/api_service.dart';

class EngineProvider extends ChangeNotifier {
  String _status = "DISCONNECTED";
  double _masterEquity = 0.0;
  double _masterProfit = 0.0;
  bool _isConnected = false;

  String get status => _status;
  double get masterEquity => _masterEquity;
  double get masterProfit => _masterProfit;
  bool get isConnected => _isConnected;

  void connectSse() {
    if (_isConnected) return;
    try {
      ApiService.getSseStream('/api/sse/stream').listen((event) {
        if (event.id == '' && event.event == '' && event.data == '') return;

        try {
          final data = json.decode(event.data ?? '{}');
          _status = data['engine_status'] ?? 'UNKNOWN';

          if (data['metrics'] != null && data['metrics']['master'] != null) {
            final master = data['metrics']['master'];
            _masterEquity = (master['equity'] ?? 0.0).toDouble();
            _masterProfit = (master['profit'] ?? 0.0).toDouble();
          }
          _isConnected = true;
          notifyListeners();
        } catch (e) {
          debugPrint("SSE JSON Error: $e");
        }
      }, onError: (e) {
        debugPrint("SSE Stream Error: $e");
        _isConnected = false;
        _status = "DISCONNECTED";
        notifyListeners();
      });
    } catch (e) {
      debugPrint("SSE Init Error: $e");
      _isConnected = false;
      notifyListeners();
    }
  }

  void disconnectSse() {
    ApiService.unsubscribeSse();
    _isConnected = false;
    _status = "DISCONNECTED";
    notifyListeners();
  }

  Future<void> toggleEngine(bool start) async {
    try {
      final action = start ? 'start' : 'stop';
      await ApiService.post('/api/system/engine', {'action': action});
    } catch (e) {
      debugPrint("Engine Action Error: $e");
      rethrow;
    }
  }
}

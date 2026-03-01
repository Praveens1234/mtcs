import 'dart:async';
import 'package:flutter/material.dart';
import 'package:mtcs_mobile/api/api_service.dart';
import 'package:mtcs_mobile/models/position_model.dart';
import 'package:mtcs_mobile/models/history_model.dart';

class TradingProvider extends ChangeNotifier {
  List<PositionModel> _positions = [];
  List<HistoryModel> _history = [];
  bool _isLoadingPositions = false;
  bool _isLoadingHistory = false;
  Timer? _pollingTimer;

  List<PositionModel> get positions => _positions;
  List<HistoryModel> get history => _history;
  bool get isLoadingPositions => _isLoadingPositions;
  bool get isLoadingHistory => _isLoadingHistory;

  void startPollingPositions() {
    fetchPositions();
    _pollingTimer = Timer.periodic(const Duration(seconds: 3), (timer) {
      fetchPositions();
    });
  }

  void stopPollingPositions() {
    _pollingTimer?.cancel();
  }

  Future<void> fetchPositions() async {
    try {
      final data = await ApiService.get('/api/trading/positions');
      if (data is List) {
        _positions = data.map((e) => PositionModel.fromJson(e)).toList();
        notifyListeners();
      }
    } catch (e) {
      debugPrint('Error fetching positions: $e');
    }
  }

  Future<void> fetchHistory({String period = 'today'}) async {
    _isLoadingHistory = true;
    notifyListeners();
    try {
      final data = await ApiService.get('/api/history/?period=$period');
      if (data != null && data['history'] is List) {
        _history = (data['history'] as List).map((e) => HistoryModel.fromJson(e)).toList();
      }
    } catch (e) {
      debugPrint('Error fetching history: $e');
    } finally {
      _isLoadingHistory = false;
      notifyListeners();
    }
  }

  Future<void> closePosition(int ticket) async {
    try {
      await ApiService.post('/api/trading/positions/close', {'ticket': ticket});
      await fetchPositions();
    } catch (e) {
      debugPrint('Error closing position $ticket: $e');
      rethrow;
    }
  }

  Future<void> executeTrade(Map<String, dynamic> payload) async {
    try {
      await ApiService.post('/api/trading/execute', payload);
      await fetchPositions();
    } catch (e) {
      debugPrint('Error executing trade: $e');
      rethrow;
    }
  }

  @override
  void dispose() {
    stopPollingPositions();
    super.dispose();
  }
}

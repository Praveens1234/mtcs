import 'dart:async';
import 'package:flutter/material.dart';
import 'package:mtcs_mobile/api/api_service.dart';
import 'package:mtcs_mobile/models/quote_model.dart';

class QuotesProvider extends ChangeNotifier {
  List<QuoteModel> _quotes = [];
  bool _isLoading = false;
  Timer? _timer;

  List<QuoteModel> get quotes => _quotes;
  bool get isLoading => _isLoading;

  void startPolling() {
    fetchQuotes();
    _timer = Timer.periodic(const Duration(seconds: 2), (timer) {
      fetchQuotes();
    });
  }

  void stopPolling() {
    _timer?.cancel();
  }

  Future<void> fetchQuotes() async {
    try {
      final data = await ApiService.get('/api/trading/quotes');
      if (data is List) {
        _quotes = data.map((e) => QuoteModel.fromJson(e)).toList();
        notifyListeners();
      }
    } catch (e) {
      debugPrint('Error fetching quotes: $e');
    }
  }

  @override
  void dispose() {
    stopPolling();
    super.dispose();
  }
}

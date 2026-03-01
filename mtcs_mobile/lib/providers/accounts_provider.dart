import 'package:flutter/material.dart';
import 'package:mtcs_mobile/api/api_service.dart';
import 'package:mtcs_mobile/models/account_model.dart';

class AccountsProvider extends ChangeNotifier {
  List<AccountModel> _accounts = [];
  bool _isLoading = false;

  List<AccountModel> get accounts => _accounts;
  List<AccountModel> get slaves => _accounts.where((a) => a.role == 'SLAVE').toList();
  AccountModel? get master => _accounts.cast<AccountModel?>().firstWhere((a) => a?.role == 'MASTER', orElse: () => null);
  bool get isLoading => _isLoading;

  Future<void> fetchAccounts() async {
    _isLoading = true;
    notifyListeners();
    try {
      final data = await ApiService.get('/api/accounts/');
      if (data is List) {
        _accounts = data.map((e) => AccountModel.fromJson(e)).toList();
      }
    } catch (e) {
      debugPrint('Error fetching accounts: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> deleteAccount(int id) async {
    try {
      await ApiService.delete('/api/accounts/$id');
      await fetchAccounts();
    } catch (e) {
      debugPrint('Error deleting account: $e');
      rethrow;
    }
  }
}

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mtcs_mobile/providers/accounts_provider.dart';
import 'package:mtcs_mobile/models/account_model.dart';

class AccountsScreen extends StatefulWidget {
  const AccountsScreen({Key? key}) : super(key: key);

  @override
  State<AccountsScreen> createState() => _AccountsScreenState();
}

class _AccountsScreenState extends State<AccountsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<AccountsProvider>(context, listen: false).fetchAccounts();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Nodes & Accounts'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => Provider.of<AccountsProvider>(context, listen: false).fetchAccounts(),
          )
        ],
      ),
      body: Consumer<AccountsProvider>(
        builder: (context, provider, child) {
          if (provider.isLoading) {
            return const Center(child: CircularProgressIndicator());
          }
          if (provider.accounts.isEmpty) {
            return const Center(child: Text('No accounts mapped.'));
          }

          return RefreshIndicator(
            onRefresh: () => provider.fetchAccounts(),
            child: ListView(
              padding: const EdgeInsets.all(16.0),
              children: [
                if (provider.master != null) ...[
                  _buildSectionHeader(context, "Master Node"),
                  _buildAccountCard(context, provider.master!, true),
                  const SizedBox(height: 24),
                ],
                if (provider.slaves.isNotEmpty) ...[
                  _buildSectionHeader(context, "Slave Nodes"),
                  ...provider.slaves.map((slave) => _buildAccountCard(context, slave, false)).toList(),
                ]
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildSectionHeader(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12.0),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.bold,
          color: Theme.of(context).colorScheme.primary,
        ),
      ),
    );
  }

  Widget _buildAccountCard(BuildContext context, AccountModel account, bool isMaster) {
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isMaster ? Theme.of(context).colorScheme.primary.withOpacity(0.5) : Theme.of(context).colorScheme.outline.withOpacity(0.2),
          width: isMaster ? 2 : 1,
        ),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.all(16),
        leading: CircleAvatar(
          backgroundColor: isMaster ? Theme.of(context).colorScheme.primaryContainer : Theme.of(context).colorScheme.secondaryContainer,
          child: Icon(
            isMaster ? Icons.star : Icons.person,
            color: isMaster ? Theme.of(context).colorScheme.onPrimaryContainer : Theme.of(context).colorScheme.onSecondaryContainer,
          ),
        ),
        title: Text(account.alias, style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text("Login: ${account.login}"),
            Text("Server: ${account.server}"),
            const SizedBox(height: 4),
            Text("State: ${account.nodeState}", style: TextStyle(color: account.nodeState == 'ACTIVE' ? Colors.green : Colors.red)),
          ],
        ),
        trailing: IconButton(
          icon: const Icon(Icons.delete_outline, color: Colors.red),
          onPressed: () {
            Provider.of<AccountsProvider>(context, listen: false).deleteAccount(account.id);
          },
        ),
      ),
    );
  }
}

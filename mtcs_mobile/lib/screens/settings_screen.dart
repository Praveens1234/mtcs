import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mtcs_mobile/providers/theme_provider.dart';
import 'package:mtcs_mobile/providers/settings_provider.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({Key? key}) : super(key: key);

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _ipController;

  @override
  void initState() {
    super.initState();
    final settings = Provider.of<SettingsProvider>(context, listen: false);
    _ipController = TextEditingController(text: settings.baseUrl);
  }

  @override
  void dispose() {
    _ipController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16.0),
          children: [
            Text('General', style: Theme.of(context).textTheme.titleSmall?.copyWith(color: Theme.of(context).colorScheme.primary)),
            const SizedBox(height: 8),
            Card(
              elevation: 0,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: Theme.of(context).colorScheme.outline.withOpacity(0.2))),
              child: SwitchListTile(
                title: const Text('Dark Theme'),
                secondary: const Icon(Icons.dark_mode_outlined),
                value: Provider.of<ThemeProvider>(context).themeMode == ThemeMode.dark,
                onChanged: (value) => Provider.of<ThemeProvider>(context, listen: false).toggleTheme(),
              ),
            ),
            const SizedBox(height: 24),
            Text('Network Configuration', style: Theme.of(context).textTheme.titleSmall?.copyWith(color: Theme.of(context).colorScheme.primary)),
            const SizedBox(height: 8),
            Card(
              elevation: 0,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: Theme.of(context).colorScheme.outline.withOpacity(0.2))),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Backend Server IP'),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _ipController,
                      decoration: const InputDecoration(border: OutlineInputBorder(), hintText: 'e.g., http://192.168.1.100:9600'),
                    ),
                    const SizedBox(height: 16),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton(
                        onPressed: () {
                          Provider.of<SettingsProvider>(context, listen: false).updateBaseUrl(_ipController.text);
                          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Network settings saved')));
                        },
                        child: const Text('Save Configuration'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('projects',Path(__file__).parents[1]/'pixel-projects.py')
projects=importlib.util.module_from_spec(spec);spec.loader.exec_module(projects)


class ProjectsTest(unittest.TestCase):
    def test_repository_input_cannot_escape_checkout_root(self):
        for value in ('../repo','owner/..','/tmp/repo','owner/repo/other','owner/repo;echo bad'):
            with self.subTest(value=value),self.assertRaises(ValueError):projects.repository_name(value)
        self.assertEqual('example/sample-project',projects.repository_name('example/sample-project'))

    def test_stop_prevents_the_next_git_or_registration_command(self):
        with patch.object(projects,'cancellation',return_value=projects.CANCEL+1),patch.object(projects.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'Stopped'):projects.command(['git','fetch'],'Fetching')
            spawn.assert_not_called()

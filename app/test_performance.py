import os
import django
import time
import unittest
import threading
from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model, authenticate
from django.db import connections
from django.test.utils import override_settings
from app.models import (
    Question,
    TestCompletion,
    Answer,
    Results,
    Category,
    Course,
    Stream
)
from users.models import UserProfile
from app.views import generate_graph

class PerformanceTest(TransactionTestCase):
    def setUp(self):
        # Create the client
        self.client = Client()
        
        # Define test users
        self.test_users = [
            {'email': 'mamta1@yopmail.com', 'password': '12345'},
            {'email': 'mansehaj_kaur_18010@yopmail.com', 'password': '12345'},
            {'email': 'mansher_sidhu_15782@yopmail.com', 'password': '12345'},
            {'email': 'mansher_sidhu_157482@yopmail.com', 'password': '12345'},
            {'email': 'mansher_sidhu_157382@yopmail.com', 'password': '12345'},
            {'email': 'mansher_sidhu_15782@yopmail.com', 'password': '12345'},
            {'email': 'mansher_sidhu_157682@yopmail.com', 'password': '12345'},
            {'email': 'mansher_sidhu_157882@yopmail.com', 'password': '12345'},
            {'email': 'mansher_sidhu_159782@yopmail.com', 'password': '12345'},
            {'email': 'sidhu_159782@yopmail.com', 'password': '12345'}
        ]

        # Create test users in test database
        User = get_user_model()
        self.db_users = []
        
        try:
            for user_data in self.test_users:
                print(f"Creating/getting user: {user_data['email']}")
                user, created = User.objects.get_or_create(
                    email=user_data['email'],
                    defaults={
                        'is_active': True
                    }
                )

                print(f"User created: {created}")
                print(f"User: {user}")
                
                if created:
                    user.set_password(user_data['password'])
                    user.save()
                self.db_users.append(user)

            # Set the main test user
            self.user = self.db_users[0]
            
            # Create or get UserProfile for main test user
            self.user_profile, profile_created = UserProfile.objects.get_or_create(
                user=self.user,
                defaults={
                    'schoolname': 'Test School',
                    'gender': '1',
                    'grade': '10'
                }
            )
            print(f"UserProfile created: {profile_created}")

            # Create or get TestCompletion
            self.test_completion, completion_created = TestCompletion.objects.get_or_create(
                user=self.user,
                defaults={
                    'test1_complete': True,
                    'test2_complete': True,
                    'test3_complete': True
                }
            )
            print(f"TestCompletion created: {completion_created}")

            # Create some test results if they don't exist
            self.create_test_results()

            # Login the main test user
            success = self.client.login(
                email=self.test_users[0]['email'],
                password=self.test_users[0]['password']
            )
            if not success:
                print("Login failed!")
                print(f"Attempting to verify user credentials...")
                user = authenticate(
                    email=self.test_users[0]['email'],
                    password=self.test_users[0]['password']
                )
                if user is None:
                    raise Exception("User authentication failed")
                raise Exception("Failed to login test user")
            else:
                print("Login successful!")

        except Exception as e:
            print(f"Setup Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise

    def create_test_results(self):
        """Create test results if they don't exist"""
        try:
            # Test 1 Results
            test1, created = Results.objects.get_or_create(
                user=self.user,
                test_paper='test1',
                defaults={
                    'scores': {'R': 80, 'I': 70, 'A': 60},
                    'results': {'Realistic': 80, 'Investigative': 70, 'Artistic': 60}
                }
            )
            print(f"Test1 results created: {created}")

            # Test 2 Results
            test2, created = Results.objects.get_or_create(
                user=self.user,
                test_paper='test2',
                defaults={
                    'scores': {'Realistic': 8, 'Investigative': 7, 'Artistic': 6}
                }
            )
            print(f"Test2 results created: {created}")

            # Test 3 Results
            test3, created = Results.objects.get_or_create(
                user=self.user,
                test_paper='test3',
                defaults={
                    'scores': {
                        'logical_score': 12,
                        'verbal_score': 8,
                        'numerical_score': 15
                    }
                }
            )
            print(f"Test3 results created: {created}")

        except Exception as e:
            print(f"Error creating test results: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise

    def test_setup(self):
        """Test if setup is working correctly"""
        print("\nTesting setup...")
        self.assertIsNotNone(self.user)
        self.assertIsNotNone(self.user_profile)
        self.assertIsNotNone(self.test_completion)
        print("Setup test completed successfully!")
    
    def measure_response_time(self, url_name, method='get', data=None, kwargs=None):
        """Measure response time for a given URL."""
        try:
            start_time = time.time()
            
            # Build the URL
            try:
                url = reverse(url_name, kwargs=kwargs)
            except Exception as e:
                print(f"Error reversing URL {url_name} with kwargs {kwargs}: {str(e)}")
                return None, None
                
            print(f"Making {method.upper()} request to: {url}")
            
            try:
                # Fixed the GET/POST logic
                if method.lower() == 'post':
                    response = self.client.post(url, data=data)
                else:  # GET request
                    response = self.client.get(url)
                    
                end_time = time.time()
                response_time = end_time - start_time
                
                print(f"{method.upper()} request completed with status code: {response.status_code}")
                
                return response_time, response.status_code
                
            except Exception as e:
                print(f"Error making request: {str(e)}")
                return None, None
                
        except Exception as e:
            print(f"Error in measure_response_time: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None, None

    def test_setup(self):
        """Test if setup is working correctly"""
        print("\nTesting setup...")
        self.assertIsNotNone(self.user)
        self.assertIsNotNone(self.user_profile)
        self.assertIsNotNone(self.test_completion)
        print("Setup test completed successfully!")

    def test_dashboard_performance(self):
        """Test dashboard view performance."""
        try:
            print("\nTesting dashboard performance...")
            response_time, status_code = self.measure_response_time('app:dashboard')
            
            self.assertIsNotNone(response_time)
            self.assertIsNotNone(status_code)
            self.assertEqual(status_code, 200)
            self.assertLess(response_time, 2.0)  # Dashboard should load within 2 seconds
            print(f"Dashboard load time: {response_time:.2f} seconds")
        except Exception as e:
            print(f"Dashboard test error: {str(e)}")
            raise

    def test_test_buttons_performance(self):
        """Test test buttons view performance."""
        try:
            print("\nTesting test buttons performance...")
            response_time, status_code = self.measure_response_time('app:test_buttons')
            
            self.assertIsNotNone(response_time)
            self.assertIsNotNone(status_code)
            self.assertEqual(status_code, 200)
            self.assertLess(response_time, 1.0)  # Should load within 1 second
            print(f"Test buttons load time: {response_time:.2f} seconds")
        except Exception as e:
            print(f"Test buttons test error: {str(e)}")
            raise

    def test_generate_pdf_performance(self):
        """Test PDF generation performance for each test paper."""
        try:
            print("\nTesting PDF generation performance...")
            test_papers = ['test1', 'test2', 'test3']
            
            for test_paper in test_papers:
                print(f"\nTesting PDF generation for {test_paper}...")
                response_time, status_code = self.measure_response_time(
                    'app:test_1',
                    method='get',  # Use GET request
                    kwargs={'test_paper': test_paper}
                )
                
                if response_time is None or status_code is None:
                    print(f"Failed to get response for {test_paper}")
                    continue
                    
                try:
                    self.assertIsNotNone(response_time)
                    self.assertIsNotNone(status_code)
                    self.assertIn(status_code, [200, 302])  # Either success or redirect
                    self.assertLess(response_time, 5.0)  # PDF generation should complete within 5 seconds
                    print(f"PDF generation time for {test_paper}: {response_time:.2f} seconds")
                except AssertionError as ae:
                    print(f"Assertion failed for {test_paper}: {str(ae)}")
                    raise
                
            # Calculate average response time only for successful requests
            successful_times = []
            for tp in test_papers:
                time_result = self.measure_response_time(
                    'app:test_1',
                    method='get',  # Use GET request
                    kwargs={'test_paper': tp}
                )
                if time_result[0] is not None:
                    successful_times.append(time_result[0])
            
            if successful_times:
                avg_time = sum(successful_times) / len(successful_times)
                print(f"\nAverage PDF generation time: {avg_time:.2f} seconds")
            else:
                print("\nNo successful requests to calculate average time")
                    
        except Exception as e:
            print(f"PDF generation test error: {str(e)}")
            print("Full error details:")
            import traceback
            print(traceback.format_exc())
            raise

    def test_test_view_performance(self):
        """Test performance of test3 view."""
        try:
            print("\nTesting test3 view performance...")
            
            # Test the main test3 view
            response_time, status_code = self.measure_response_time('app:test3_view')
            
            self.assertIsNotNone(response_time)
            self.assertIsNotNone(status_code)
            self.assertEqual(status_code, 200)
            self.assertLess(response_time, 2.0)  # Test view should load within 2 seconds
            print(f"test3_view load time: {response_time:.2f} seconds")

        except Exception as e:
            print(f"Test view performance error: {str(e)}")
            print("Full error details:")
            import traceback
            print(traceback.format_exc())
            raise

    def test_graph_generation_performance(self):
        """Test graph generation performance."""
        try:
            print("\nTesting graph generation performance...")
            start_time = time.time()
            
            below, avg, above_avg, personality, min_length, max_length = generate_graph(self)
            
            end_time = time.time()
            generation_time = end_time - start_time
            
            self.assertLess(generation_time, 3.0)  # Graph generation should complete within 3 seconds
            print(f"Graph generation time: {generation_time:.2f} seconds")
        except Exception as e:
            print(f"Graph generation test error: {str(e)}")
            raise

    def test_concurrent_requests(self):
        """Test performance under concurrent requests."""
        try:
            print("\nTesting concurrent requests performance...")
            def make_request(user_data):
                try:
                    client = Client()
                    logged_in = client.login(
                        email=user_data['email'],
                        password=user_data['password']
                    )
                    if logged_in:
                        return client.get(reverse('app:dashboard'))
                    else:
                        print(f"Failed to login user: {user_data['email']}")
                except Exception as e:
                    print(f"Error in concurrent request: {str(e)}")

            threads = []
            start_time = time.time()
            
            for user_data in self.test_users:
                thread = threading.Thread(target=make_request, args=(user_data,))
                thread.start()
                threads.append(thread)
            
            for thread in threads:
                thread.join()
                
            end_time = time.time()
            total_time = end_time - start_time
            
            self.assertLess(total_time, 10.0)  # Concurrent requests should complete within 10 seconds
            print(f"Concurrent requests completion time: {total_time:.2f} seconds")
        except Exception as e:
            print(f"Concurrent requests test error: {str(e)}")
            raise

    def test_database_query_performance(self):
        """Test database query performance."""
        try:
            print("\nTesting database query performance...")
            start_time = time.time()
            
            # Perform common database queries
            questions_count = Question.objects.all().count()
            results = Results.objects.filter(user=self.user).select_related('user').all()
            test_completion = TestCompletion.objects.get(user=self.user)
            
            end_time = time.time()
            query_time = end_time - start_time
            
            self.assertLess(query_time, 1.0)  # Database queries should complete within 1 second
            print(f"Database query time: {query_time:.2f} seconds")
            print(f"Number of questions: {questions_count}")
            print(f"Number of results: {len(results)}")
        except Exception as e:
            print(f"Database query test error: {str(e)}")
            raise

def run_all_tests():
    """Run all performance tests"""
    suite = unittest.TestLoader().loadTestsFromTestCase(PerformanceTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

def run_specific_test(test_name):
    """Run a specific test by name"""
    suite = unittest.TestSuite()
    suite.addTest(PerformanceTest(test_name))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

if __name__ == '__main__':
    # Setup Django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteen.settings')
    django.setup()
    
    # You can either run all tests:
    run_all_tests()

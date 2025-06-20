using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Linq;

namespace TestNamespace
{
    /// <summary>
    /// Represents a user in the system
    /// </summary>
    public interface IUser
    {
        int Id { get; set; }
        string Name { get; set; }
        string Email { get; set; }
        bool IsActive { get; set; }
    }

    /// <summary>
    /// Repository interface for user operations
    /// </summary>
    public interface IUserRepository
    {
        Task<IUser> FindByIdAsync(int id);
        Task<IUser> SaveAsync(IUser user);
        Task<IEnumerable<IUser>> GetAllAsync();
    }

    /// <summary>
    /// Base service class providing common functionality
    /// </summary>
    public abstract class BaseService
    {
        protected readonly ILogger _logger;

        protected BaseService(ILogger logger)
        {
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        }

        public abstract Task InitializeAsync();

        protected virtual void LogInfo(string message)
        {
            _logger.LogInformation(message);
        }
    }

    /// <summary>
    /// User entity implementation
    /// </summary>
    public class User : IUser
    {
        public int Id { get; set; }
        public string Name { get; set; }
        public string Email { get; set; }
        public bool IsActive { get; set; }
        
        private DateTime _createdDate;
        public static int TotalUsers { get; private set; }

        public User()
        {
            _createdDate = DateTime.UtcNow;
            TotalUsers++;
        }

        public User(string name, string email) : this()
        {
            Name = name ?? throw new ArgumentNullException(nameof(name));
            Email = email ?? throw new ArgumentNullException(nameof(email));
            IsActive = true;
        }

        public void Activate()
        {
            IsActive = true;
        }

        public void Deactivate()
        {
            IsActive = false;
        }

        public override string ToString()
        {
            return $"User[{Id}]: {Name} ({Email})";
        }

        public static void ResetUserCount()
        {
            TotalUsers = 0;
        }
    }

    /// <summary>
    /// Service for managing users
    /// </summary>
    public sealed class UserService : BaseService, IUserRepository
    {
        private readonly List<IUser> _users;
        private static UserService _instance;

        public UserService(ILogger logger) : base(logger)
        {
            _users = new List<IUser>();
        }

        public static UserService GetInstance(ILogger logger)
        {
            if (_instance == null)
            {
                _instance = new UserService(logger);
            }
            return _instance;
        }

        public override async Task InitializeAsync()
        {
            LogInfo("UserService initializing...");
            await Task.Delay(100);
            LogInfo("UserService initialized");
        }

        public async Task<IUser> FindByIdAsync(int id)
        {
            if (id <= 0)
                throw new ArgumentException("ID must be positive", nameof(id));

            await Task.Delay(10);
            return _users.FirstOrDefault(u => u.Id == id);
        }

        public async Task<IUser> SaveAsync(IUser user)
        {
            if (user == null)
                throw new ArgumentNullException(nameof(user));

            await Task.Delay(10);
            
            var existingUser = _users.FirstOrDefault(u => u.Id == user.Id);
            if (existingUser != null)
            {
                var index = _users.IndexOf(existingUser);
                _users[index] = user;
            }
            else
            {
                user.Id = _users.Count + 1;
                _users.Add(user);
            }

            return user;
        }

        public async Task<IEnumerable<IUser>> GetAllAsync()
        {
            await Task.Delay(10);
            return _users.ToList();
        }
    }

    public static class UserFactory
    {
        public static IUser CreateUser(string name, string email, bool isActive = true)
        {
            if (string.IsNullOrWhiteSpace(name))
                throw new ArgumentException("Name cannot be null or empty", nameof(name));
            
            return new User(name, email) { IsActive = isActive };
        }
    }
}

public interface ILogger
{
    void LogInformation(string message);
    void LogError(string message);
} 